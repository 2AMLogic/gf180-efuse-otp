v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/vsource.sym} 0 0 0 0 {name=Vdd value="DC 5.0"}
C {devices/lab_pin.sym} 0 -30 0 0 {name=l1 lab=vdd}
C {devices/lab_pin.sym} 0 30 0 0 {name=l2 lab=0}
C {devices/vcvs.sym} 200 0 0 0 {name=Eg value=1}
C {devices/lab_pin.sym} 200 -30 0 0 {name=l3 lab=g}
C {devices/lab_pin.sym} 200 30 0 0 {name=l4 lab=0}
C {devices/lab_pin.sym} 160 -20 0 0 {name=l5 lab=vdd}
C {devices/lab_pin.sym} 160 20 0 0 {name=l6 lab=0}
C {devices/vsource.sym} 400 -200 0 0 {name=Vi value="DC 0"}
C {devices/lab_pin.sym} 400 -230 0 0 {name=l7 lab=vdd}
C {devices/lab_pin.sym} 400 -170 0 0 {name=l8 lab=na}
C {devices/res.sym} 400 -100 0 0 {name=Rfuse value=200 footprint=none}
C {devices/lab_pin.sym} 400 -130 0 0 {name=l9 lab=na}
C {devices/lab_pin.sym} 400 -70 0 0 {name=l10 lab=nb}
C {devices/res.sym} 550 -100 0 0 {name=Rr value=20 footprint=none}
C {devices/lab_pin.sym} 550 -130 0 0 {name=l11 lab=nb}
C {devices/lab_pin.sym} 550 -70 0 0 {name=l12 lab=d}
C {symbols/nfet_06v0.sym} 700 0 0 0 {name=Xsel L=0.7u W=10u nf=1 m=1 model=nfet_06v0 spiceprefix=X}
C {devices/lab_pin.sym} 720 -30 0 0 {name=l13 lab=d}
C {devices/lab_pin.sym} 680 0 0 0 {name=l14 lab=g}
C {devices/lab_pin.sym} 720 30 0 0 {name=l15 lab=0}
C {devices/lab_pin.sym} 720 0 0 0 {name=l16 lab=0}
T {Program-select bench, one cell. Rfuse is shown at 200 ohm; the PDK efuse subcircuit (pblow=0) stands in for it in the 200 ohm run, a plain resistor at 140/260. Rr (routing resistance) and Eg (gate = program supply) are ASSUMPTIONS. The swept deck is cell.cir.in; W is swept by run.sh.} -100 -300 0 0 0.3 0.3 {}
