// Run in Neo4j Browser after `python -m backend.sync_graph`.

// Find banks directly dependent on the Payment Rail.
MATCH (bank:RiskInstitution)-[edge:DEPENDS_ON]->(service:RiskInfrastructure {name: 'Payment Rail'})
RETURN bank.name, edge.loss ORDER BY bank.name;

// Aggregate: number of banks depending on each service.
MATCH (service:RiskInfrastructure)
OPTIONAL MATCH (bank:RiskInstitution)-[:DEPENDS_ON]->(service)
RETURN service.name, count(bank) AS dependent_banks
ORDER BY dependent_banks DESC, service.name;

// Aggregate: creditors' total exposure to each debtor bank.
MATCH (debtor:RiskInstitution)
OPTIONAL MATCH (creditor:RiskInstitution)-[edge:EXPOSED_TO]->(debtor)
RETURN debtor.name, coalesce(sum(toFloat(edge.amount)), 0) AS creditor_exposure
ORDER BY creditor_exposure DESC, debtor.name;

// Candidate operational-to-financial paths (actual loss requires a simulation).
MATCH (service:RiskInfrastructure {name: 'Payment Rail'})<-[:DEPENDS_ON]-(origin:RiskInstitution)
MATCH path=(target:RiskInstitution)-[:EXPOSED_TO*0..5]->(origin)
RETURN service.name, [node IN reverse(nodes(path)) | node.name] AS bank_path
ORDER BY length(path) LIMIT 20;
