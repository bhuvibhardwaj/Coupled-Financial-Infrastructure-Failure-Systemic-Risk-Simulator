-- Run this file only for the DBMS demonstration; it is not part of app setup.
-- The temporary table leaves no permanent data behind.
CREATE TEMP TABLE dbms_demo (id integer PRIMARY KEY, label text NOT NULL);
ALTER TABLE dbms_demo ADD COLUMN score numeric(5,2) DEFAULT 0;
INSERT INTO dbms_demo (id, label, score) VALUES (1, 'draft', 10);
UPDATE dbms_demo SET label = 'checked', score = 25 WHERE id = 1;
SELECT * FROM dbms_demo ORDER BY id;
DELETE FROM dbms_demo WHERE id = 1;
DROP TABLE dbms_demo;

-- JOIN: scenario, service, and creator of each run.
SELECT r.id, s.name AS scenario, i.name AS failed_service,
       u.name AS created_by, r.risk_score
FROM simulation_runs r
JOIN scenarios s ON s.id = r.scenario_id
JOIN infrastructure i ON i.id = s.failed_infrastructure_id
LEFT JOIN users u ON u.id = r.created_by
ORDER BY r.created_at DESC;

-- GROUP BY, aggregate, and HAVING: banks with average stress above 25%.
SELECT i.name, COUNT(*) AS runs, ROUND(AVG(ri.stress_pct), 2) AS avg_stress
FROM run_impacts ri
JOIN institutions i ON i.id = ri.institution_id
GROUP BY i.id, i.name
HAVING AVG(ri.stress_pct) > 25
ORDER BY avg_stress DESC;

-- Subquery: runs with risk above the overall average.
SELECT r.id, r.risk_score
FROM simulation_runs r
WHERE r.risk_score > (SELECT AVG(risk_score) FROM simulation_runs)
ORDER BY r.risk_score DESC;

-- Stored function and view used by the web application.
SELECT run_id, scenario_name, risk_score FROM v_run_summary ORDER BY run_id DESC;
SELECT r.id, calculate_systemic_risk(r.id) AS recalculated_score
FROM simulation_runs r ORDER BY r.id DESC LIMIT 5;

-- Transaction demonstration: this deliberately rolls back.
BEGIN;
INSERT INTO scenarios (name, failed_infrastructure_id, severity)
SELECT 'Rollback demonstration', id, 10 FROM infrastructure ORDER BY id LIMIT 1;
ROLLBACK;
