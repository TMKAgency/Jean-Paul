CREATE TABLE Tasks (

id INT IDENTITY(1,1) PRIMARY KEY,
assigned_to VARCHAR(255),
assigned_by VARCHAR(255),
task_text NVARCHAR(500),
completed BIT DEFAULT 0,
created_at DATETIME DEFAULT GETDATE()

);