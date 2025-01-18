
- `File name`: My-Agreements-in-4i-Tip-Sheet_508-1.pdf
- `File size`: 432.5 KiB
- `Pages`: 11
- `Description`: the file mostly contains text.

| Result Type        | Old s3fs            | Asynchronous        |     Time diff        |
|--------------------|---------------------|---------------------|----------------------|
| Markdown Extraction| 0 min 10 sec 709 ms | 0 min 9 sec 669 ms  | 1 sec 40 ms faster   |
| Force OCR          | 0 min 25 sec 255 ms | 0 min 25 sec 307 ms | 52 ms slower         |
| Plain Text         | 0 min 7 sec 61 ms   | 0 min 4 sec 236 ms  | 2 sec 825 ms faster  |

<br>

---

- `File name`: 2024 Sales Presentation C6501-PPOs-1.pdf
- `File size`: 3.6 MiB
- `Pages`: 31
- `Description`: all the page are images except the last page which is text.


| Result Type        | Old s3fs            | Asynchronous        |         Time diff         |
|--------------------|---------------------|---------------------|---------------------------|
| Markdown Extraction| 0 min 56 sec 196 ms | 0 min 51 sec 514 ms | 0 min 4 sec 682 ms faster |
| Force OCR          | 0 min 59 sec 586 ms | 0 min 53 sec 42 ms  | 0 min 6 sec 544 ms faster |
| Plain Text         | 0 min 15 sec 216 ms | 0 min 9 sec 229 ms  | 0 min 5 sec 987 ms faster |

<br>

---

- `File name`:  CMS_AI_Playbook_3_Final.pdf
- `File size`: 4.1 MiB
- `Pages`: 108
- `Description`: the file contains both images and text with more than 100 pages.

| Result Type        | Old s3fs            |     Asynchronous     |       Time diff        |
|--------------------|---------------------|----------------------|------------------------|
| Markdown Extraction| 0 min 56 sec 832 ms |  0 min 56 sec 431 ms |  401 ms faster         |
| Force OCR          | 4 min 0 sec 723 ms  | 4 min 2 sec 172 ms   |  1 sec 449 ms  slower  |
| Plain Text         | 0 min 27 sec 299 ms | 0 min 14 sec 130 ms  |  13 sec 169 ms faster  |

 <br>

---


# Docling parsing

| **Attempt**          | **My-Agreements-in-4i-Tip-Sheet_508-1.pdf** | **2024 Sales Presentation C6501-PPOs-1.pdf** | **CMS_AI_Playbook_3_Final.pdf** |
|-----------------------|---------------------------------------------|---------------------------------------------|---------------------------------|
| **1st**              | 0 min 14 sec 85 ms                         | 1 min 27 sec 548 ms                         | 1 min 3 sec 775 ms             |
| **2nd**              | 0 min 13 sec 858 ms                        | 1 min 13 sec 652 ms                         | 1 min 0 sec 839 ms             |
| **3rd**              | 0 min 13 sec 91 ms                         | 1 min 26 sec 656 ms                         | 1 min 0 sec 658 ms             |
| **4th**              | 0 min 13 sec 842 ms                        | 1 min 12 sec 919 ms                         | 0 min 59 sec 648 ms            |
| **5th**              | 0 min 12 sec 524 ms                        | 1 min 14 sec 204 ms                         | 1 min 2 sec 614 ms             |
| **Average**          | 0 min 13 sec 480 ms                        | 1 min 18 sec 996 ms                         | 1 min 1 sec 507 ms             |
