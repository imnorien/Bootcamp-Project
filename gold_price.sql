
CREATE DATABASE IF NOT EXISTS db_gold_price;
USE db_gold_price;

CREATE TABLE IF NOT EXISTS accounts (
    account_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
    prediction_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT,
    open_price FLOAT NOT NULL,
    prev_price FLOAT NOT NULL,
    avg_7 FLOAT NOT NULL,
    predicted_price FLOAT NOT NULL,
    price_change FLOAT,
    chart_base64 LONGTEXT, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS price_alerts (
    alert_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT,
    prediction_id INT,
    alert_msg VARCHAR(255),
    alert_time DATETIME,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
);

DELIMITER //
CREATE TRIGGER trg_before_insert_price_change
BEFORE INSERT ON predictions
FOR EACH ROW
BEGIN
    IF NEW.price_change IS NULL THEN
        SET NEW.price_change = NEW.open_price - NEW.prev_price;
    END IF;
END;
//
DELIMITER ;


DELIMITER //
CREATE TRIGGER trg_after_insert_prediction_alert
AFTER INSERT ON predictions
FOR EACH ROW
BEGIN
    IF ABS(NEW.price_change) > 50 THEN
        INSERT INTO price_alerts (account_id, prediction_id, alert_msg, alert_time)
        VALUES (
            NEW.account_id,
            NEW.prediction_id,
            CONCAT('⚠️ Significant price change: $', NEW.price_change),
            NOW()
        );
    END IF;
END;
//
DELIMITER ;


DELIMITER //
CREATE PROCEDURE insert_prediction (
    IN p_account_id INT,
    IN p_open FLOAT,
    IN p_prev FLOAT,
    IN p_avg7 FLOAT,
    IN p_predicted FLOAT
)
BEGIN
    DECLARE v_change FLOAT;
    SET v_change = p_open - p_prev;

    INSERT INTO predictions (
        account_id, open_price, prev_price, avg_7, predicted_price, price_change
    )
    VALUES (
        p_account_id, p_open, p_prev, p_avg7, p_predicted, v_change
    );
END;
//
DELIMITER ;
