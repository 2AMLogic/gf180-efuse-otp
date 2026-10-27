v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} 0 40 0 0 {name=p0 lab=bl}
C {devices/ipin.sym} 0 70 0 0 {name=p1 lab=wl}
C {devices/iopin.sym} 0 100 0 0 {name=p2 lab=vss}
C {efuse_prim.sym} 250 200 0 0 {name=Xf model=efuse pblow=0 spiceprefix=X}
C {devices/lab_pin.sym} 250 170 0 0 {name=l1 lab=bl}
C {devices/lab_pin.sym} 250 230 0 0 {name=l2 lab=n}
C {symbols/nfet_06v0.sym} 470 200 0 0 {name=Xsel L=0.7u W=60u nf=1 m=1 model=nfet_06v0 spiceprefix=X}
C {devices/lab_pin.sym} 490 170 0 0 {name=l4 lab=n}
C {devices/lab_pin.sym} 450 200 0 0 {name=l5 lab=wl}
C {devices/lab_pin.sym} 490 230 0 0 {name=l6 lab=vss}
C {devices/lab_pin.sym} 490 200 0 0 {name=l7 lab=vss}
T {Fuse bitcell: PDK efuse subcircuit in series with a 5V/6V-oxide NMOS select (W=60u L=0.7u, the width from design/README.md program-select result).} 0 -60 0 0 0.3 0.3 {}
