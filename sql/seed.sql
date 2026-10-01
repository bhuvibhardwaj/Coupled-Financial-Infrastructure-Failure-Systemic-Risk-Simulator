INSERT INTO institutions (id, name, liquidity_buffer) VALUES
    (1, 'Bank A', 100), (2, 'Bank B', 50), (3, 'Bank C', 75),
    (4, 'Bank D', 90), (5, 'Bank E', 80), (6, 'Bank F', 110)
ON CONFLICT (id) DO NOTHING;

INSERT INTO infrastructure (id, name, category) VALUES
    (1, 'Payment Rail', 'Payments'),
    (2, 'Cloud Platform', 'Technology'),
    (3, 'Clearing House', 'Clearing'),
    (4, 'Market Data Feed', 'Data')
ON CONFLICT (id) DO NOTHING;

INSERT INTO dependencies (institution_id, infrastructure_id, loss_at_full_failure) VALUES
    (1, 1, 120), (3, 2, 50), (4, 2, 20),
    (5, 3, 30), (6, 3, 15), (1, 4, 20), (4, 4, 25)
ON CONFLICT DO NOTHING;

INSERT INTO exposures (creditor_id, debtor_id, amount, recovery_rate) VALUES
    (2, 1, 80, 0.25), (3, 2, 90, 0.20), (4, 3, 60, 0.20),
    (5, 4, 40, 0.25), (6, 5, 50, 0.20)
ON CONFLICT DO NOTHING;

SELECT setval(pg_get_serial_sequence('institutions', 'id'),
              (SELECT max(id) FROM institutions));
SELECT setval(pg_get_serial_sequence('infrastructure', 'id'),
              (SELECT max(id) FROM infrastructure));
