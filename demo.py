"""Particle shot sideways from the bottom left, steered around a loop by corner magnetic fields,
inside a box of absorbing walls."""
from elements import Detector, ElectricField, MagneticField, Wall
from simulator import ParticleSimulator2D, ParticleSource

sim = ParticleSimulator2D(ParticleSource(x=5.9, y=3, px=0.5, py=0.0, sigma_px=0.00001, sigma_py=0.00001), seed=1)
# Absorbing walls around the 10 x 10 domain.
sim.add_element(Wall(-0.5, -0.5, 10.5, 0))
sim.add_element(Wall(-0.5, 10, 10.5, 10.5))
sim.add_element(Wall(-0.5, -0.5, 0, 10.5))
sim.add_element(Wall(10, -0.5, 10.5, 10.5))
# bz = -0.5 with q = m = 1 and |p| = 1 gives radius 2: each 4 x 4 box turns the beam a quarter turn counter-clockwise.
sim.add_element(MagneticField(6, 0, 10, 4, bz=-0.5))
sim.add_element(MagneticField(6, 6, 10, 10, bz=-0.5))
sim.add_element(MagneticField(0, 6, 4, 10, bz=-0.5))
sim.add_element(MagneticField(0, 0, 4, 4, bz=-0.5))
# One accelerator cell fills each gap between magnets: detector, electric field along the beam, detector.
E = 0.02
cells = {
    "B": ((4, 0, 4.5, 4), (4.5, 0, 5.5, 4), (5.5, 0, 6, 4), (E, 0.0)),
    "R": ((6, 4, 10, 4.5), (6, 4.5, 10, 5.5), (6, 5.5, 10, 6), (0.0, E)),
    "T": ((5.5, 6, 6, 10), (4.5, 6, 5.5, 10), (4, 6, 4.5, 10), (-E, 0.0)),
    "L": ((0, 5.5, 4, 6), (0, 4.5, 4, 5.5), (0, 4, 4, 4.5), (0.0, -E)),
}
for name, (entry, field, exit_, (ex, ey)) in cells.items():
    sim.add_element(Detector(*entry, id=f"{name}1"))
    sim.add_element(ElectricField(*field, ex=ex, ey=ey))
    sim.add_element(Detector(*exit_, id=f"{name}2"))

result = sim.simulate(T=500.0, n_steps=3000)
print(f"alive at end: {int(result.alive[-1].sum())}/{result.alive.shape[1]}")
for ev in result.events:
    print(f"t={ev.time:.2f}  particle={ev.particle}  detector={ev.detector_id}  duration={ev.duration:.2f}")
print(sim.savefig("demo_config.png", result))
print(sim.animate(result, "demo.gif", fps=30, stride=10))
