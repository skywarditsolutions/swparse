# swparse benchmark

# Markdown Extraction

### Test 1

- `File name`: My-Agreements-in-4i-Tip-Sheet_508-1.pdf
- `File size`: 432.5 KiB
- `Pages`: 11
- `Description`: the file mostly contains text.


| Metric         | Markdown Extraction   |     Force OCR       |    Plain Text       | 
|----------------|-----------------------|---------------------|---------------------|
| 1st Attempt    | 0 min 8 sec 609 ms    | 0 min 22 sec 296 ms | 0 min 3 sec 256 ms  |
| 2nd Attempt    | 0 min 9 sec 54 ms     | 0 min 23 sec 559 ms | 0 min 3 sec 866 ms  |
| 3rd Attempt    | 0 min 7 sec 757 ms    | 0 min 22 sec 944 ms | 0 min 3 sec 484 ms  |
| 4th Attempt    | 0 min 9 sec 194 ms    | 0 min 22 sec 151 ms | 0 min 4 sec 2 ms    |
| 5th Attempt    | 0 min 9 sec 73 ms     | 0 min 23 sec 907 ms | 0 min 3 sec 665 ms  |
|                |                       |                     |                     |
| Avg Time       | `0 min 8 sec 937 ms`  |`0 min 22 sec 971 ms`|`0 min 3 sec 421 ms` |


#### Memory Usage 

| Process              | Markdown     | force_ocr    | plain_text |
| ---------------------| ------------ | ------------ | ---------- |
| Before parsing pdf   | 864.46 MB    | 855.18 MB    | 844.02 MB  |
| Modle storage on VRAM| 860.38 MB    | 855.18 MB    | 844.02 MB  |
| After parsing pdf    | 1336.91 MB  | 1396.24 MB   | ---        |
| End of parsing pdf   | 2328.97 MB   | 2190.67 MB   | 859.04 MB  |
|                      |              |              |            |
| Memory usage         | `1170.89 MB` | `1335.49 MB` | `15.02 MB` |

---

### Test 2

- `File name`: 2024 Sales Presentation C6501-PPOs.pdf  
- `File size`: 3.6 MiB
- `Pages`: 31
- `Description`: all the page are images except the last page which is text.

| Metric         |  Markdown Extraction  |     Force OCR        |    Plain Text       | 
|----------------|-----------------------|----------------------|---------------------|
| 1st Attempt    | 0 min 46 sec 821 ms   | 0 min 47 sec 331 ms  |0 min 5 sec 654 ms   |
| 2nd Attempt    | 0 min 47 sec 411 ms   | 0 min 51 sec 17 ms   |0 min 10 sec 512 ms  |
| 3rd Attempt    | 0 min 50 sec 800 ms   | 0 min 52 sec 212 ms  |0 min 7 sec 577 ms   |
| 4th Attempt    | 0 min 46 sec 545 ms   | 0 min 48 sec 242 ms  |0 min 8 sec 300 ms   |
| 5th Attempt    | 0 min 47 sec 285 ms   | 0 min 52 sec 495 ms  |0 min 4 sec 387 ms   |
|                |                       |                      |                     |
| Avg Time       | `0 min 47 sec 772 ms` | `0 min 50 sec 259 ms`|`0 min 7 sec 286 ms` |

#### Memory Usage 
 
| Process            | Memory usage | force_ocr    | plain_text |
| ------------------ | ------------ | ------------ | ---------- |
| Before parsing pdf | 860.38 MB    | 860.54 MB    | 867.04 MB  |
| After Model loaded | 1380.74 MB   | 1401.60 MB   | ---        |
| End of parsing pdf | 2587.70 MB   | 2666.20 MB   | 867.17 MB  |
|                    |              |              |            |
| Memory usage       | `1727.32 MB` | `1805.66 MB` | `0.13 MB`  |

---

### Test 3

- `File name`: CMS_AI_Playbook_3_Final.pdf 
- `File size`: 4.1 MiB
- `Pages`: 108
- `Description`: the file contains both images and text with more than 100 pages.

| Metric         |   Markdown Extraction       |     Force OCR        |    Plain Text       | 
|----------------|-----------------------------|----------------------|---------------------|
| 1st Attempt    | 0 min 58 sec 482 ms         | 3 min 57 sec 234 ms  |  0 min 4 sec 98 ms  |
| 2nd Attempt    | 0 min 58 sec 335 ms         | 3 min 54 sec 15 ms   |  0 min 3 sec 937 ms |
| 3rd Attempt    | 0 min 58 sec 35 ms          | 3 min 56 sec 234 ms  |  0 min 4 sec 792 ms |
| 4th Attempt    | 0 min 52 sec 171 ms         | 3 min 58 sec 151 ms  |  0 min 3 sec 985 ms |
| 5th Attempt    | 1 min 0 sec 656 ms          | 3 min 56 sec 682 ms  |  0 min 3 sec 143 ms |
|                |                             |                      |                     |
| Avg Time       | `0 min 57 sec 535 ms`       |`3 min 56 sec 463 ms` |`0 min 3 sec 991 ms` |

#### Memory Usage 

| Process            | Memory usage | force_ocr | plain_text |
| ------------------ | ------------ | --------- | ---------- |
| Before parsing pdf | 860.88 MB    |880.55 MB  | 867.17 MB  |
| After Model loaded | 1401.60 MB   |1411.45 MB |    ---     |
| End of parsing pdf | 3937.88 MB   |4263.92 MB | 884.55 MB  |
|                    |              |           |            |
| Memory usage       | 3077.00 MB   |3383.37 MB | `17.38 MB` |

## Findings

When working with rich text files, enabling the `force_ocr` option significantly increases processing time.However, for image-rich files, the difference in time between enabling and disabling `force_ocr` is negligible. In the latest Marker v1.2.3 update, the Surya OCR has been improved; it can now intelligently decide whether reapplying OCR is necessary.



# Concurrent testing

Bombarding http://52.202.108.42:8000 with 10000 requests using 150 connections:

| Metric                | Value            |
| --------------------- | ---------------- |
| Requests/sec          | 54.98            |
| Requests/sec Stdev    | 60.75            |
| Max Requests/sec      | 576.37           |
| Latency (Avg)         | 1.80s            |
| Latency (Stdev)       | 7.63s            |
| Max Latency           | 2.31m            |
| 1xx HTTP Codes        | 0                |
| 2xx HTTP Codes        | 9969             |
| 3xx HTTP Codes        | 0                |
| 4xx HTTP Codes        | 0                |
| 5xx HTTP Codes        | 0                |
| Other HTTP Codes      | 31               |
| Timeout Errors        | 15               |
| I/O Timeout Errors    | 4                |
| Throughput            | 800.66KB/s       |
