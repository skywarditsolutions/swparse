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



## Findings

When working with rich text files, enabling the `force_ocr` option significantly increases processing time.However, for image-rich files, the difference in time between enabling and disabling `force_ocr` is negligible. In the latest Marker v1.2.3 update, the Surya OCR has been improved; it can now intelligently decide whether reapplying OCR is necessary.