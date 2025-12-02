-- email مايبقاش فارغ
ALTER TABLE users
ALTER COLUMN email SET NOT NULL;

-- email مايتكرّرش
ALTER TABLE users
ADD CONSTRAINT users_email_key UNIQUE (email);

-- role يكون غير admin أو employee
ALTER TABLE users
ADD CONSTRAINT users_role_check
CHECK (role IN ('admin', 'employee'));
