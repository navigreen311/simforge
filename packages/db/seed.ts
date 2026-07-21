// SimForge dev seed — blueprint §B.5.
// 13 departments, ~20 agents, 2 Packs (Greenstone, MedLink Pro), ~6 scenarios,
// Constitution v1.0.0, and ObjectRegistry entries.
//
// WEEK 1: currently a skeleton that seeds departments + a few agents so the app boots.
// Full scenario/pack seeding lands with the Pack ingestion feature (see docs/ROADMAP.md, Phase 3).

import { PrismaClient } from "../../apps/web/src/lib/db/generated";

const prisma = new PrismaClient();

const DEPARTMENTS: Array<{ villageKey: string; name: string; totalAgents: number }> = [
  { villageKey: "Engineering", name: "Engineering", totalAgents: 12 },
  { villageKey: "Recruitment", name: "Recruitment", totalAgents: 10 },
  { villageKey: "Compliance", name: "Compliance", totalAgents: 8 },
  { villageKey: "Payroll", name: "Payroll", totalAgents: 6 },
  { villageKey: "Sales", name: "Sales", totalAgents: 9 },
  { villageKey: "CustomerSuccess", name: "Customer Success", totalAgents: 7 },
  { villageKey: "Clinical", name: "Clinical Operations", totalAgents: 11 },
  { villageKey: "Finance", name: "Finance", totalAgents: 6 },
  { villageKey: "Marketing", name: "Marketing", totalAgents: 8 },
  { villageKey: "Operations", name: "Operations", totalAgents: 9 },
  { villageKey: "Legal", name: "Legal", totalAgents: 4 },
  { villageKey: "Data", name: "Data & Analytics", totalAgents: 8 },
  { villageKey: "Executive", name: "Executive", totalAgents: 8 },
];

// A small representative subset of Village agents for dev.
const AGENTS: Array<{ villageAgentId: string; name: string; role: string; dept: string }> = [
  { villageAgentId: "taylor_zhang", name: "Taylor Zhang", role: "Senior Engineer", dept: "Engineering" },
  { villageAgentId: "jennifer_adams", name: "Jennifer Adams", role: "Recruiter", dept: "Recruitment" },
  { villageAgentId: "marcus_reed", name: "Marcus Reed", role: "Compliance Analyst", dept: "Compliance" },
  { villageAgentId: "priya_patel", name: "Priya Patel", role: "Payroll Specialist", dept: "Payroll" },
  { villageAgentId: "david_kim", name: "David Kim", role: "Account Executive", dept: "Sales" },
  { villageAgentId: "sara_lopez", name: "Sara Lopez", role: "CSM", dept: "CustomerSuccess" },
  { villageAgentId: "nina_okafor", name: "Nina Okafor", role: "Clinical Coordinator", dept: "Clinical" },
  { villageAgentId: "gardner", name: "Gardner", role: "Executive Agent", dept: "Executive" },
];

async function main() {
  console.log("Seeding departments…");
  const deptByKey = new Map<string, string>();
  for (const d of DEPARTMENTS) {
    const dept = await prisma.department.upsert({
      where: { villageKey: d.villageKey },
      update: { name: d.name, totalAgents: d.totalAgents },
      create: d,
    });
    deptByKey.set(d.villageKey, dept.id);
  }

  console.log("Seeding agents…");
  for (const a of AGENTS) {
    const departmentId = deptByKey.get(a.dept);
    if (!departmentId) continue;
    await prisma.agent.upsert({
      where: { villageAgentId: a.villageAgentId },
      update: { name: a.name, role: a.role, departmentId },
      create: {
        villageAgentId: a.villageAgentId,
        name: a.name,
        role: a.role,
        departmentId,
        gardnerFlag: a.villageAgentId === "gardner",
        level10Enabled: a.villageAgentId === "gardner",
      },
    });

    await prisma.objectRegistryEntry.upsert({
      where: { urn: `urn:gc:village:agent:${a.villageAgentId}` },
      update: {},
      create: {
        urn: `urn:gc:village:agent:${a.villageAgentId}`,
        kind: "agent",
        canonicalId: a.villageAgentId,
        metadata: { name: a.name, role: a.role, department: a.dept },
      },
    });
  }

  console.log(`Seeded ${DEPARTMENTS.length} departments and ${AGENTS.length} agents.`);
  // WEEK 1: Packs, scenarios, and Constitution v1.0.0 seeding are added in Phase 3.
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
