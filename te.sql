UPDATE app_settings
SET last_export_month = NULL,
    last_export_at = NULL
WHERE id = 1;