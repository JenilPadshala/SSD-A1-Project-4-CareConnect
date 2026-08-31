-- ============================================================
-- Workflow 1: Atomic Appointment
-- Safely deduct HSA balance and create an appointment.
-- The existing HSA audit trigger logs the deduction.
-- ============================================================

CREATE OR REPLACE PROCEDURE create_appointment_atomic(
    IN p_patient_id UUID,
    IN p_clinic_id UUID,
    IN p_copay_amount DECIMAL(10,2)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_hsa_balance DECIMAL(10,2);
    v_clinic_accepting BOOLEAN;
BEGIN

    -- 1. Validate copay
    IF p_copay_amount <= 0 THEN
        RAISE EXCEPTION 'Copay amount must be greater than zero';
    END IF;


    -- 2. Lock the patient row.
    -- This prevents two simultaneous appointments
    -- from spending the same HSA balance.
    SELECT hsa_balance
    INTO v_hsa_balance
    FROM patients
    WHERE id = p_patient_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Patient % does not exist', p_patient_id;
    END IF;


    -- 3. Lock and check the clinic.
    SELECT is_accepting_patients
    INTO v_clinic_accepting
    FROM clinics
    WHERE id = p_clinic_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Clinic % does not exist', p_clinic_id;
    END IF;

    IF NOT v_clinic_accepting THEN
        RAISE EXCEPTION 'Clinic % is not accepting patients', p_clinic_id;
    END IF;


    -- 4. Check sufficient HSA balance.
    IF v_hsa_balance < p_copay_amount THEN
        RAISE EXCEPTION
            'Insufficient HSA balance. Available: %, Required: %',
            v_hsa_balance,
            p_copay_amount;
    END IF;


    -- 5. Deduct the copay.
    -- The existing AFTER UPDATE trigger automatically
    -- creates the wallet audit record.
    UPDATE patients
    SET hsa_balance = hsa_balance - p_copay_amount
    WHERE id = p_patient_id;


    -- 6. Create the appointment.
    INSERT INTO appointments (
        patient_id,
        clinic_id,
        copay_amount,
        status
    )
    VALUES (
        p_patient_id,
        p_clinic_id,
        p_copay_amount,
        'WAITING'
    );

END;
$$;