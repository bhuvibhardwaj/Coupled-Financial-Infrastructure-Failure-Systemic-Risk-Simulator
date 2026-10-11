import { Network } from "../lib/api";

export function NetworkGraph({ network }: { network: Network }) {
  const serviceX = new Map(network.services.map((service, index) =>
    [service.id, 100 + index * (800 / Math.max(1, network.services.length - 1))]));
  const bankX = new Map(network.banks.map((bank, index) =>
    [bank.id, 80 + index * (840 / Math.max(1, network.banks.length - 1))]));
  return <div className="graph-wrap">
    <svg viewBox="0 0 1000 390" role="img" aria-label="Services, banks, dependency lines, and exposure arrows">
      <defs><marker id="risk-arrow" viewBox="0 0 10 10" refX="9" refY="5"
        markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#c66b35" /></marker></defs>
      {network.dependencies.map(edge => <line key={`${edge.bank_id}-${edge.service_id}`}
        x1={bankX.get(edge.bank_id)} y1="252" x2={serviceX.get(edge.service_id)} y2="95"
        stroke="#9fc1c8" strokeWidth="2" />)}
      {network.exposures.map((edge, index) => {
        const x1 = bankX.get(edge.creditor_id) ?? 0;
        const x2 = bankX.get(edge.debtor_id) ?? 0;
        const bend = 330 + (index % 3) * 17;
        return <path key={`${edge.creditor_id}-${edge.debtor_id}`}
          d={`M ${x1} 289 Q ${(x1 + x2) / 2} ${bend} ${x2} 289`}
          fill="none" stroke="#c66b35" strokeWidth="2" strokeDasharray="5 4"
          markerEnd="url(#risk-arrow)" />;
      })}
      {network.services.map(service => <g key={service.id}>
        <rect x={(serviceX.get(service.id) ?? 0) - 67} y="45" width="134" height="50"
          rx="12" fill="#d9eeee" stroke="#71aeb6" />
        <text x={serviceX.get(service.id)} y="75" textAnchor="middle" fontSize="14"
          fill="#164f58">{service.name}</text>
      </g>)}
      {network.banks.map(bank => <g key={bank.id}>
        <circle cx={bankX.get(bank.id)} cy="270" r="27" fill="#e9eef7" stroke="#a5b7d2" />
        <text x={bankX.get(bank.id)} y="275" textAnchor="middle" fontSize="13"
          fill="#263f66">{bank.name}</text>
      </g>)}
      <text x="20" y="28" fontSize="13" fill="#627789">Services</text>
      <text x="20" y="232" fontSize="13" fill="#627789">Banks</text>
      <text x="20" y="376" fontSize="12" fill="#627789">Solid = dependency · Dashed arrow = creditor exposed to debtor</text>
    </svg>
  </div>;
}
