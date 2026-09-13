# Limitations and integration requirements

TXT and DOCX files were written and reopened using deterministic provider responses; paragraphs, basic bold styling and table cells were checked. Live translation quality and provider connectivity were not tested.

The local requirements include both supported provider clients. Configure your own Google Cloud credentials or `DEEPL_API_KEY` in the ignored local `.env`. Translation sends document text to the selected provider.

Keep web services bound to `127.0.0.1`. Hosting this application for multiple users requires authentication and separate storage and resource limits.
