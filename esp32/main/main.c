/* SPDX-License-Identifier: Apache-2.0
 * Original Gabriel bridge client. No Muse account, SDK token or proprietary protocol.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <time.h>
#include <sys/time.h>
#include "sdkconfig.h"
#include "cJSON.h"
#include "audio.h"
#include "driver/gpio.h"
#include "esp_crt_bundle.h"
#include "esp_event.h"
#include "esp_http_client.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_partition.h"
#include "esp_random.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "mbedtls/base64.h"
#include "nvs_flash.h"
#include "nvs.h"

#define MAX_REPLY (2 * 1024 * 1024)
static const char *personas[]={"boli","kai","chakri","lane","sherma","nest","juno","lina","emil","nora","archer","cole","paya","mirav"};
static char ssid[33], password[65], origin[256], device_token[128], persona[49]="boli", backend[12]="fixture", last_op[65];
static char ca[8192];
static char time_server[128];
static bool time_started=false;
static bool connected=false, uncertain=false;
static nvs_handle_t config_nvs;
static SemaphoreHandle_t mutex;

/* Development XTS keys are generated in the key partition. No eFuse is burned.
 * Production must protect that partition with reviewed secure provisioning.
 */
static esp_err_t initialize_nvs(void) {
    const esp_partition_t *partition=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_NVS_KEYS,"nvs_keys");
    if (!partition) return ESP_ERR_NOT_FOUND;
    nvs_sec_cfg_t security={0};
    esp_err_t error=nvs_flash_read_security_cfg(partition,&security);
    if (error==ESP_ERR_NVS_KEYS_NOT_INITIALIZED) error=nvs_flash_generate_keys(partition,&security);
    if (error!=ESP_OK) return error;
    return nvs_flash_secure_init(&security);
}

typedef struct { char *bytes; size_t size; bool overflow; } response_buffer;

static esp_err_t collect_response(esp_http_client_event_t *event) {
    response_buffer *buffer=event->user_data;
    if (event->event_id==HTTP_EVENT_ON_DATA && event->data_len>0) {
        if (buffer->size + event->data_len > MAX_REPLY) { buffer->overflow=true; return ESP_ERR_NO_MEM; }
        char *next=realloc(buffer->bytes,buffer->size+event->data_len+1);
        if (!next) { buffer->overflow=true; return ESP_ERR_NO_MEM; }
        buffer->bytes=next;
        memcpy(buffer->bytes+buffer->size,event->data,event->data_len);
        buffer->size+=event->data_len; buffer->bytes[buffer->size]=0;
    }
    return ESP_OK;
}

static cJSON *request(const char *path, const char *body, int *status) {
    char url[384], authorization[160];
    snprintf(url,sizeof(url),"%s%s",origin,path);
    snprintf(authorization,sizeof(authorization),"Bearer %s",device_token);
    response_buffer buffer={0};
    esp_http_client_config_t settings={.url=url,.timeout_ms=120000,.event_handler=collect_response,
        .user_data=&buffer,.disable_auto_redirect=true,.cert_pem=ca[0]?ca:NULL,
        .crt_bundle_attach=ca[0]?NULL:esp_crt_bundle_attach,.buffer_size=4096,.buffer_size_tx=4096};
    esp_http_client_handle_t client=esp_http_client_init(&settings);
    if (!client) return NULL;
    esp_http_client_set_header(client,"Authorization",authorization);
    esp_http_client_set_header(client,"Content-Type","application/json");
    if (body) { esp_http_client_set_method(client,HTTP_METHOD_POST); esp_http_client_set_post_field(client,body,strlen(body)); }
    esp_err_t error=esp_http_client_perform(client);
    *status=esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);
    cJSON *result=NULL;
    if (error==ESP_OK && !buffer.overflow && buffer.bytes) result=cJSON_Parse(buffer.bytes);
    free(buffer.bytes);
    memset(authorization,0,sizeof(authorization));
    return result;
}

static void save_uncertain(bool value) {
    uncertain=value; nvs_set_u8(config_nvs,"uncertain",value?1:0); nvs_set_str(config_nvs,"last_op",last_op); nvs_commit(config_nvs);
}

static void show_result(cJSON *result) {
    cJSON *text=cJSON_GetObjectItemCaseSensitive(result,"text");
    cJSON *status=cJSON_GetObjectItemCaseSensitive(result,"status");
    if (cJSON_IsString(text)) printf("GADGET_REPLY %s\n",text->valuestring);
    else if (cJSON_IsString(status)) printf("GADGET_STATUS %s\n",status->valuestring);
    cJSON *audio=cJSON_GetObjectItemCaseSensitive(result,"audio");
    cJSON *encoded=audio?cJSON_GetObjectItemCaseSensitive(audio,"base64"):NULL;
    cJSON *mime=audio?cJSON_GetObjectItemCaseSensitive(audio,"mime"):NULL;
    if (cJSON_IsString(encoded) && cJSON_IsString(mime) && !strcmp(mime->valuestring,"audio/wav")) {
        size_t size=0;
        mbedtls_base64_decode(NULL,0,&size,(const unsigned char *)encoded->valuestring,strlen(encoded->valuestring));
        uint8_t *bytes=malloc(size);
        if (bytes && mbedtls_base64_decode(bytes,size,&size,(const unsigned char *)encoded->valuestring,strlen(encoded->valuestring))==0) {
            if (gadget_play_wav(bytes,size)!=ESP_OK) printf("GADGET_AUDIO_UNAVAILABLE reply retained as text\n");
        }
        free(bytes);
    }
    cJSON_DeleteItemFromObjectCaseSensitive(result,"audio");
    char *json=cJSON_PrintUnformatted(result);
    if (json) { printf("GADGET_RESULT %s\n",json); free(json); }
}

static void recover(void) {
    if (!last_op[0]) { printf("GADGET_NO_PENDING_TURN\n"); return; }
    char path[128]; snprintf(path,sizeof(path),"/v1/turns/%s",last_op);
    int status=0; cJSON *receipt=request(path,NULL,&status);
    if (receipt && status==200) {
        cJSON *state=cJSON_GetObjectItemCaseSensitive(receipt,"status");
        cJSON *result=cJSON_GetObjectItemCaseSensitive(receipt,"result");
        if (cJSON_IsString(state) && !strcmp(state->valuestring,"done") && cJSON_IsObject(result)) {
            show_result(result); save_uncertain(false);
        } else printf("GADGET_REVIEW_REQUIRED operation=%s\n",last_op);
    } else printf("GADGET_RECOVERY_STATUS http=%d operation=%s (no automatic replay)\n",status,last_op);
    cJSON_Delete(receipt);
}

static void turn(const char *text, bool microphone) {
    if (!connected || !device_token[0] || !origin[0]) { printf("GADGET_NOT_READY provision Wi-Fi and device credential\n"); return; }
    if (uncertain) { printf("GADGET_REVIEW_REQUIRED operation=%s; use recover or reviewed-clear\n",last_op); return; }
    if (time(NULL)<1577836800) { printf("GADGET_CLOCK_REQUIRED provision a clock or LAN time server before TLS\n"); return; }
    cJSON *body=cJSON_CreateObject();
    snprintf(last_op,sizeof(last_op),"esp-%08lx%08lx%08lx%08lx",(unsigned long)esp_random(),(unsigned long)esp_random(),
             (unsigned long)esp_random(),(unsigned long)esp_random());
    cJSON_AddStringToObject(body,"operationId",last_op); cJSON_AddStringToObject(body,"persona",persona);
    cJSON_AddStringToObject(body,"backend",backend); cJSON_AddStringToObject(body,"text",text);
#if CONFIG_GADGET_MIC_ENABLED
    if (microphone && strcmp(backend,"fixture")) {
        uint8_t *wav=NULL; size_t wav_size=0;
        esp_err_t error=gadget_record_wav(&wav,&wav_size,CONFIG_GADGET_BUTTON_GPIO);
        if (error!=ESP_OK) { printf("GADGET_RECORDING_FAILED\n"); cJSON_Delete(body); return; }
        size_t encoded_size=((wav_size+2)/3)*4+1, written=0; unsigned char *encoded=malloc(encoded_size);
        if (!encoded || mbedtls_base64_encode(encoded,encoded_size,&written,wav,wav_size)!=0) {
            free(wav); free(encoded); cJSON_Delete(body); printf("GADGET_RECORDING_FAILED\n"); return;
        }
        encoded[written]=0; cJSON_AddStringToObject(body,"audioBase64",(char *)encoded);
        cJSON_AddStringToObject(body,"audioMime","audio/wav"); free(encoded); free(wav);
#if CONFIG_GADGET_SPEAKER_ENABLED
        cJSON_AddBoolToObject(body,"speak",true); cJSON_AddStringToObject(body,"audioFormat","wav");
#endif
    }
#else
    (void)microphone;  /* The basic button sends a text turn to any configured backend. */
#endif
    char *payload=cJSON_PrintUnformatted(body); cJSON_Delete(body);
    if (!payload) { printf("GADGET_NO_MEMORY\n"); return; }
    save_uncertain(true);  /* Persist before sending. Wi-Fi reconnect never replays this POST. */
    if (CONFIG_GADGET_STATUS_GPIO>=0) gpio_set_level(CONFIG_GADGET_STATUS_GPIO,1);
    printf("GADGET_WORKING persona=%s backend=%s operation=%s\n",persona,backend,last_op);
    int status=0; cJSON *result=request("/v1/turns",payload,&status); free(payload);
    if (result && status==200) { show_result(result); save_uncertain(false); }
    else printf("GADGET_TURN_HELD http=%d operation=%s; inspect receipt before a new turn\n",status,last_op);
    cJSON_Delete(result);
    if (CONFIG_GADGET_STATUS_GPIO>=0) gpio_set_level(CONFIG_GADGET_STATUS_GPIO,0);
}

static void wifi_event(void *arg, esp_event_base_t base, int32_t event, void *data) {
    (void)arg; (void)data;
    if (base==WIFI_EVENT && event==WIFI_EVENT_STA_START) esp_wifi_connect();
    if (base==WIFI_EVENT && event==WIFI_EVENT_STA_DISCONNECTED) { connected=false; esp_wifi_connect(); }
    if (base==IP_EVENT && event==IP_EVENT_STA_GOT_IP) {
        connected=true;
        if (time_server[0] && !time_started) {
            esp_sntp_config_t clock_config=ESP_NETIF_SNTP_DEFAULT_CONFIG(time_server);
            if (esp_netif_sntp_init(&clock_config)==ESP_OK) time_started=true;
        }
        printf("GADGET_CONNECTED persona=%s backend=%s\n",persona,backend);
    }
}

static void wifi_start(void) {
    ESP_ERROR_CHECK(esp_netif_init()); ESP_ERROR_CHECK(esp_event_loop_create_default()); esp_netif_create_default_wifi_sta();
    wifi_init_config_t init=WIFI_INIT_CONFIG_DEFAULT(); ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT,ESP_EVENT_ANY_ID,wifi_event,NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT,IP_EVENT_STA_GOT_IP,wifi_event,NULL));
    wifi_config_t config={0}; memcpy(config.sta.ssid,ssid,strlen(ssid)); memcpy(config.sta.password,password,strlen(password));
    config.sta.threshold.authmode=WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA)); ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA,&config)); ESP_ERROR_CHECK(esp_wifi_start());
}

static void load_string(const char *key, char *out, size_t maximum) { size_t size=maximum; nvs_get_str(config_nvs,key,out,&size); }

static bool portable_id(const char *value) {
    if (!value || !value[0]) return false;
    for (const char *c=value; *c; c++) if (!((*c>='a' && *c<='z') || (*c>='0' && *c<='9') || *c=='-')) return false;
    return true;
}

static void provision(cJSON *object) {
    const char *keys[]={"ssid","password","origin","deviceToken","caPem","persona","backend"};
    char *outputs[]={ssid,password,origin,device_token,ca,persona,backend};
    const size_t sizes[]={sizeof(ssid),sizeof(password),sizeof(origin),sizeof(device_token),sizeof(ca),sizeof(persona),sizeof(backend)};
    for (int i=0;i<7;i++) {
        cJSON *value=cJSON_GetObjectItemCaseSensitive(object,keys[i]);
        if (!cJSON_IsString(value) || strlen(value->valuestring)>=sizes[i]) { printf("GADGET_PROVISION_REJECTED invalid field\n"); return; }
    }
    cJSON *clock=cJSON_GetObjectItemCaseSensitive(object,"clockEpoch");
    cJSON *time_host=cJSON_GetObjectItemCaseSensitive(object,"timeServer");
    if (!cJSON_IsNumber(clock) || clock->valuedouble<1577836800 ||
        !cJSON_IsString(time_host) || strlen(time_host->valuestring)>=sizeof(time_server)) {
        printf("GADGET_PROVISION_REJECTED clock configuration required\n"); return;
    }
    const char *uri=cJSON_GetObjectItemCaseSensitive(object,"origin")->valuestring;
    const char *bearer=cJSON_GetObjectItemCaseSensitive(object,"deviceToken")->valuestring;
    const char *who=cJSON_GetObjectItemCaseSensitive(object,"persona")->valuestring;
    const char *mode=cJSON_GetObjectItemCaseSensitive(object,"backend")->valuestring;
    if (strncmp(uri,"https://",8) || strncmp(bearer,"gdev_",5) || !portable_id(who) ||
        (strcmp(mode,"fixture") && strcmp(mode,"cloud") && strcmp(mode,"local"))) {
        printf("GADGET_PROVISION_REJECTED HTTPS and device-scoped configuration required\n"); return;
    }
    for (int i=0;i<7;i++) {
        strcpy(outputs[i],cJSON_GetObjectItemCaseSensitive(object,keys[i])->valuestring);
        if (nvs_set_str(config_nvs,keys[i],outputs[i])!=ESP_OK) { printf("GADGET_PROVISION_FAILED storage\n"); return; }
    }
    strcpy(time_server,time_host->valuestring);
    nvs_set_str(config_nvs,"timeServer",time_server);
    nvs_set_u64(config_nvs,"clockEpoch",(uint64_t)clock->valuedouble);
    if (nvs_commit(config_nvs)!=ESP_OK) { printf("GADGET_PROVISION_FAILED commit\n"); return; }
    printf("GADGET_PROVISIONED restart to connect\n");
}

static void console(void *unused) {
    (void)unused; char *line=calloc(1,16384);
    if (!line) { vTaskDelete(NULL); return; }
    while (true) {
        if (!fgets(line,16384,stdin)) { vTaskDelay(pdMS_TO_TICKS(50)); clearerr(stdin); continue; }
        line[strcspn(line,"\r\n")]=0;
        xSemaphoreTake(mutex,portMAX_DELAY);
        if (line[0]=='{') { cJSON *json=cJSON_Parse(line); if (json) provision(json); else printf("GADGET_PROVISION_REJECTED JSON\n"); cJSON_Delete(json); }
        else if (!strncmp(line,"persona ",8) && portable_id(line+8) && strlen(line+8)<sizeof(persona)) {
            strcpy(persona,line+8); nvs_set_str(config_nvs,"persona",persona); nvs_commit(config_nvs); printf("GADGET_PERSONA %s\n",persona);
        } else if (!strncmp(line,"backend ",8) && (!strcmp(line+8,"fixture") || !strcmp(line+8,"cloud") || !strcmp(line+8,"local"))) {
            strcpy(backend,line+8); nvs_set_str(config_nvs,"backend",backend); nvs_commit(config_nvs); printf("GADGET_BACKEND %s\n",backend);
        } else if (!strncmp(line,"text ",5)) turn(line+5,false);
        else if (!strcmp(line,"recover")) recover();
        else if (!strcmp(line,"reviewed-clear")) { save_uncertain(false); printf("GADGET_REVIEW_ACKNOWLEDGED no prior turn replayed\n"); }
        else if (!strcmp(line,"catalog")) { int status=0; cJSON *result=request("/v1/catalog",NULL,&status); if(result) show_result(result); cJSON_Delete(result); }
        else if (!strcmp(line,"personas")) {
            for (unsigned int i=0;i<sizeof(personas)/sizeof(personas[0]);i++) printf("GADGET_EXAMPLE %s\n",personas[i]);
        }
        else printf("GADGET_COMMANDS persona ID | backend fixture/cloud/local | text MESSAGE | catalog | recover | reviewed-clear\n");
        memset(line,0,16384); xSemaphoreGive(mutex);
    }
}

void app_main(void) {
    esp_err_t error=initialize_nvs();
    if (error==ESP_ERR_NVS_NO_FREE_PAGES || error==ESP_ERR_NVS_NEW_VERSION_FOUND) {
        /* Keep credentials and pending receipts until explicit owner reset. */
        printf("GADGET_STORAGE_RECOVERY_REQUIRED do not erase automatically\n"); return;
    }
    ESP_ERROR_CHECK(error); ESP_ERROR_CHECK(nvs_open("gadget",NVS_READWRITE,&config_nvs));
    load_string("ssid",ssid,sizeof(ssid)); load_string("password",password,sizeof(password)); load_string("origin",origin,sizeof(origin));
    load_string("deviceToken",device_token,sizeof(device_token)); load_string("caPem",ca,sizeof(ca));
    load_string("persona",persona,sizeof(persona)); load_string("backend",backend,sizeof(backend)); load_string("last_op",last_op,sizeof(last_op));
    load_string("timeServer",time_server,sizeof(time_server));
    uint64_t clock_epoch=0;
    if (nvs_get_u64(config_nvs,"clockEpoch",&clock_epoch)==ESP_OK) {
        struct timeval clock_value={.tv_sec=(time_t)clock_epoch}; settimeofday(&clock_value,NULL);
    }
    uint8_t held=0; nvs_get_u8(config_nvs,"uncertain",&held); uncertain=held!=0;
    mutex=xSemaphoreCreateMutex();
    gpio_config_t button={.pin_bit_mask=1ULL<<CONFIG_GADGET_BUTTON_GPIO,.mode=GPIO_MODE_INPUT,.pull_up_en=GPIO_PULLUP_ENABLE};
    ESP_ERROR_CHECK(gpio_config(&button));
    if (CONFIG_GADGET_STATUS_GPIO>=0) { gpio_set_direction(CONFIG_GADGET_STATUS_GPIO,GPIO_MODE_OUTPUT); }
    xTaskCreate(console,"gadget-console",16384,NULL,5,NULL);
    printf("GADGET_READY provision through USB; credentials are never printed\n");
    if (ssid[0] && origin[0] && device_token[0]) wifi_start();
    while (true) {
        if (gpio_get_level(CONFIG_GADGET_BUTTON_GPIO)==0) {
            vTaskDelay(pdMS_TO_TICKS(40));
            if (gpio_get_level(CONFIG_GADGET_BUTTON_GPIO)==0) {
                xSemaphoreTake(mutex,portMAX_DELAY);
                turn("Prepare the domain example for review.",true);
                xSemaphoreGive(mutex);
                while (gpio_get_level(CONFIG_GADGET_BUTTON_GPIO)==0) vTaskDelay(pdMS_TO_TICKS(20));
            }
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}
