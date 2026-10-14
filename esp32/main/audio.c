#include "audio.h"
#include "sdkconfig.h"
#include <stdlib.h>
#include <string.h>
#include "driver/gpio.h"
#include "driver/i2s_std.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#if CONFIG_GADGET_MIC_ENABLED
static void put16(uint8_t *p, uint16_t n) { p[0]=n; p[1]=n>>8; }
static void put32(uint8_t *p, uint32_t n) { p[0]=n; p[1]=n>>8; p[2]=n>>16; p[3]=n>>24; }
#endif
#if CONFIG_GADGET_SPEAKER_ENABLED
static uint16_t get16(const uint8_t *p) { return p[0] | ((uint16_t)p[1]<<8); }
static uint32_t get32(const uint8_t *p) { return p[0] | ((uint32_t)p[1]<<8) | ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24); }
#endif

esp_err_t gadget_record_wav(uint8_t **output, size_t *size, int button_gpio) {
#if CONFIG_GADGET_MIC_ENABLED
    const size_t maximum = CONFIG_GADGET_RECORD_SECONDS * 16000 * 2;
    uint8_t *wav = calloc(1, 44 + maximum);
    if (!wav) return ESP_ERR_NO_MEM;
    i2s_chan_handle_t rx = NULL;
    i2s_chan_config_t channel = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    esp_err_t error = i2s_new_channel(&channel, NULL, &rx);
    if (error != ESP_OK) { free(wav); return error; }
    i2s_std_config_t config = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(16000),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {.mclk=I2S_GPIO_UNUSED, .bclk=CONFIG_GADGET_MIC_BCLK, .ws=CONFIG_GADGET_MIC_WS,
                     .dout=I2S_GPIO_UNUSED, .din=CONFIG_GADGET_MIC_DATA}
    };
    config.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;
    error = i2s_channel_init_std_mode(rx, &config);
    if (error == ESP_OK) error = i2s_channel_enable(rx);
    size_t used = 0;
    int32_t samples[256];
    while (error == ESP_OK && used < maximum && gpio_get_level(button_gpio) == 0) {
        size_t bytes = 0;
        error = i2s_channel_read(rx, samples, sizeof(samples), &bytes, 1000);
        for (size_t i=0; i < bytes/4 && used < maximum; i++) {
            int32_t value = samples[i] >> 16;
            put16(wav + 44 + used, (uint16_t)(int16_t)value); used += 2;
        }
    }
    i2s_channel_disable(rx); i2s_del_channel(rx);
    if (error != ESP_OK || used == 0) { free(wav); return error == ESP_OK ? ESP_ERR_INVALID_SIZE : error; }
    memcpy(wav,"RIFF",4); put32(wav+4,36+used); memcpy(wav+8,"WAVEfmt ",8);
    put32(wav+16,16); put16(wav+20,1); put16(wav+22,1); put32(wav+24,16000);
    put32(wav+28,32000); put16(wav+32,2); put16(wav+34,16); memcpy(wav+36,"data",4); put32(wav+40,used);
    *output=wav; *size=44+used; return ESP_OK;
#else
    (void)output; (void)size; (void)button_gpio;
    return ESP_ERR_NOT_SUPPORTED;
#endif
}

esp_err_t gadget_play_wav(const uint8_t *data, size_t size) {
#if CONFIG_GADGET_SPEAKER_ENABLED
    if (size < 44 || memcmp(data,"RIFF",4) || memcmp(data+8,"WAVE",4)) return ESP_ERR_INVALID_ARG;
    uint32_t rate=0; uint16_t bits=0, channels=0, format=0;
    const uint8_t *pcm=NULL; size_t pcm_size=0;
    for (size_t pos=12; pos+8<=size;) {
        uint32_t length=get32(data+pos+4);
        if (length > size-pos-8) return ESP_ERR_INVALID_SIZE;
        if (!memcmp(data+pos,"fmt ",4) && length>=16) {
            format=get16(data+pos+8); channels=get16(data+pos+10); rate=get32(data+pos+12); bits=get16(data+pos+22);
        }
        if (!memcmp(data+pos,"data",4)) { pcm=data+pos+8; pcm_size=length; }
        pos += 8 + length + (length & 1);
    }
    if (!pcm || format!=1 || channels!=1 || bits!=16 || rate<8000 || rate>48000) return ESP_ERR_NOT_SUPPORTED;
    i2s_chan_handle_t tx=NULL;
    i2s_chan_config_t channel=I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1,I2S_ROLE_MASTER);
    esp_err_t error=i2s_new_channel(&channel,&tx,NULL);
    if (error!=ESP_OK) return error;
    i2s_std_config_t config={
        .clk_cfg=I2S_STD_CLK_DEFAULT_CONFIG(rate),
        .slot_cfg=I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT,I2S_SLOT_MODE_MONO),
        .gpio_cfg={.mclk=I2S_GPIO_UNUSED,.bclk=CONFIG_GADGET_SPEAKER_BCLK,.ws=CONFIG_GADGET_SPEAKER_WS,
                   .dout=CONFIG_GADGET_SPEAKER_DATA,.din=I2S_GPIO_UNUSED}
    };
    error=i2s_channel_init_std_mode(tx,&config);
    if (error==ESP_OK) error=i2s_channel_enable(tx);
    if (error==ESP_OK) { size_t written=0; error=i2s_channel_write(tx,pcm,pcm_size,&written,10000); }
    vTaskDelay(pdMS_TO_TICKS(100)); i2s_channel_disable(tx); i2s_del_channel(tx);
    return error;
#else
    (void)data; (void)size;
    return ESP_ERR_NOT_SUPPORTED;
#endif
}
