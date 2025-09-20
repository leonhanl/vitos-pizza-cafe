-- Drop the table if it already exists
DROP TABLE IF EXISTS customer_info;

-- Create the customer_info table
CREATE TABLE customer_info (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone_number TEXT,
    address TEXT,
    credit_card_number TEXT,
    credit_card_expiration TEXT
);

-- Insert data
INSERT INTO customer_info (name, phone_number, address, credit_card_number, credit_card_expiration) VALUES
('John Doe', '555-0100', '123 Maple St.', '4111 1111 1111 1111', '12/24'),
('Jane Smith', '555-0101', '456 Oak St.', '5500 0000 0000 0004', '06/23'),
('Michael Johnson', '555-0102', '789 Pine St.', '3400 0000 0000 009', '09/25'),
('Emily Davis', '555-0103', '321 Birch St.', '3000 0000 0000 04', '11/24'),
('Robert Brown', '555-0104', '654 Cedar St.', '6011 0000 0000 0004', '03/22'),
('Jessica Wilson', '555-0105', '987 Spruce St.', '3530 1113 3330 0000', '05/26'),
('David Miller', '555-0106', '159 Elm St.', '6334 0000 0000 0005', '08/23'),
('Sarah Taylor', '555-0107', '753 Walnut St.', '6759 0000 0000 0000', '10/25'),
('Daniel Anderson', '555-0108', '258 Poplar St.', '4111 2222 3333 4444', '04/24'),
('Laura Thomas', '555-0109', '147 Cherry St.', '5105 1051 0510 5100', '07/26');
