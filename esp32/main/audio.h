#pragma once
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
esp_err_t gadget_record_wav(uint8_t **output, size_t *size, int button_gpio);
esp_err_t gadget_play_wav(const uint8_t *data, size_t size);
