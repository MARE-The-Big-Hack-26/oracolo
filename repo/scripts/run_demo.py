"""Demo da terminale: confronto tra modalità e un caso passo-passo sul magazzino (CAD)."""
from oracolo.bench import run_batch, to_markdown
from oracolo.sim import run_scenario
from oracolo.warehouse import DEFAULT_CAMERAS, warehouse_scenario

print(to_markdown(run_batch(30, 1, configs={"2 camere sugli incroci": DEFAULT_CAMERAS})))
r = run_scenario(warehouse_scenario(), "oracolo", log=True)
for row in r.log[::10]:
    print(f"t={row['t']:5.2f}s  x={row['s']:5.2f}m  v={row['v']*3.6:4.1f} km/h  limite={row['limit']*3.6:4.1f}  livello={row['level']}  {row['cause']}")
print("collisione:", r.collision, "| distanza minima:", round(r.min_dist, 2), "m")
