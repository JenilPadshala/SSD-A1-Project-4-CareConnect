-- trigger function definitino
CREATE OR REPLACE FUNCTION log_hsa_balance_change()
RETURNS TRIGGER AS $$
BEGIN
    -- only log if the balance actually changed
    IF NEW.hsa_balance <> OLD.hsa_balance THEN
        INSERT INTO wallet_audit_logs (
            patient_id,
            amount_changed,
            action_type,
            balance_after
        ) VALUES (
            NEW.id,
            ABS(NEW.hsa_balance - OLD.hsa_balance), -- Ensures positive amount
            CASE 
                WHEN NEW.hsa_balance > OLD.hsa_balance THEN 'CREDIT'
                ELSE 'DEBIT'
            END,
            NEW.hsa_balance
        );
    END IF;
    
    RETURN NEW; -- required for row-level triggers
END;
$$ LANGUAGE plpgsql;

-- bind the trigger to the patients table
CREATE TRIGGER trigger_audit_hsa_balance
AFTER UPDATE OF hsa_balance ON patients
FOR EACH ROW
EXECUTE FUNCTION log_hsa_balance_change();