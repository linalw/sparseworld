# Errors and Recovery

| Date | Trigger | Impact | Containment | Recovery | Validation evidence |
|---|---|---|---|---|---|
| 2026-08-27 | DOCX visual renderer could not find LibreOffice/soffice on the local runtime PATH | DOCX page-image QA could not be completed in this environment | Rebuilt the DOCX and checked OOXML structure plus content parity; PDF was rendered and visually inspected separately | Install/provide LibreOffice, then run the packaged DOCX renderer before hardware handoff | DOCX generation exit 0; PDF 13 pages rendered; structural checks passed; visual DOCX QA remains open |
