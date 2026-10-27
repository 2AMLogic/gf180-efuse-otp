v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} 0 40 0 0 {name=p0 lab=bl[7:0]}
C {devices/ipin.sym} 0 70 0 0 {name=p1 lab=wl}
C {devices/iopin.sym} 0 100 0 0 {name=p2 lab=vss}
C {efuse_bitcell.sym} 250 200 0 0 {name=Xb[7:0]}
C {devices/lab_pin.sym} 170 200 0 0 {name=l1 lab=bl[7:0]}
C {devices/lab_pin.sym} 170 220 0 0 {name=l2 lab=wl}
C {devices/lab_pin.sym} 170 240 0 0 {name=l3 lab=vss}
T {One array row: 8 bitcells sharing wl; bit n of the row is column n.} 0 -60 0 0 0.3 0.3 {}
