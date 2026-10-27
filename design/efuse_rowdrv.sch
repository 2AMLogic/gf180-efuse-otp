v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/ipin.sym} 0 40 0 0 {name=p0 lab=row_sel}
C {devices/opin.sym} 0 70 0 0 {name=p1 lab=wl}
C {devices/iopin.sym} 0 100 0 0 {name=p2 lab=vdd33}
C {devices/iopin.sym} 0 130 0 0 {name=p3 lab=vprog}
C {devices/iopin.sym} 0 160 0 0 {name=p4 lab=vss}
C {efuse_ls.sym} 250 200 0 0 {name=Xls}
C {devices/lab_pin.sym} 170 200 0 0 {name=l1 lab=row_sel}
C {devices/lab_pin.sym} 170 220 0 0 {name=l2 lab=wl}
C {devices/lab_pin.sym} 170 240 0 0 {name=l3 lab=vdd33}
C {devices/lab_pin.sym} 170 260 0 0 {name=l4 lab=vprog}
C {devices/lab_pin.sym} 170 280 0 0 {name=l5 lab=vss}
T {Row driver: wl = row_sel level-shifted to vprog (5V gate drive for the select device).} 0 -60 0 0 0.3 0.3 {}
