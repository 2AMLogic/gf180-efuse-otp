v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/ipin.sym} 0 40 0 0 {name=p0 lab=in}
C {devices/opin.sym} 0 70 0 0 {name=p1 lab=out}
C {devices/iopin.sym} 0 100 0 0 {name=p2 lab=vdd33}
C {devices/iopin.sym} 0 130 0 0 {name=p3 lab=vprog}
C {devices/iopin.sym} 0 160 0 0 {name=p4 lab=vss}
C {symbols/pfet_03v3.sym} 250 200 0 0 {name=Mpi L=0.28u W=2u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 270 170 0 0 {name=l1 lab=vdd33}
C {devices/lab_pin.sym} 230 200 0 0 {name=l2 lab=in}
C {devices/lab_pin.sym} 270 230 0 0 {name=l3 lab=inb}
C {devices/lab_pin.sym} 270 200 0 0 {name=l4 lab=vdd33}
C {symbols/nfet_03v3.sym} 470 200 0 0 {name=Mni L=0.28u W=1u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 490 170 0 0 {name=l6 lab=inb}
C {devices/lab_pin.sym} 450 200 0 0 {name=l7 lab=in}
C {devices/lab_pin.sym} 490 230 0 0 {name=l8 lab=vss}
C {devices/lab_pin.sym} 490 200 0 0 {name=l9 lab=vss}
C {symbols/nfet_06v0.sym} 690 200 0 0 {name=Mn1 L=0.7u W=4u nf=1 m=1 model=nfet_06v0 spiceprefix=X}
C {devices/lab_pin.sym} 710 170 0 0 {name=l11 lab=x1}
C {devices/lab_pin.sym} 670 200 0 0 {name=l12 lab=in}
C {devices/lab_pin.sym} 710 230 0 0 {name=l13 lab=vss}
C {devices/lab_pin.sym} 710 200 0 0 {name=l14 lab=vss}
C {symbols/nfet_06v0.sym} 910 200 0 0 {name=Mn2 L=0.7u W=4u nf=1 m=1 model=nfet_06v0 spiceprefix=X}
C {devices/lab_pin.sym} 930 170 0 0 {name=l16 lab=out}
C {devices/lab_pin.sym} 890 200 0 0 {name=l17 lab=inb}
C {devices/lab_pin.sym} 930 230 0 0 {name=l18 lab=vss}
C {devices/lab_pin.sym} 930 200 0 0 {name=l19 lab=vss}
C {symbols/pfet_06v0.sym} 1130 200 0 0 {name=Mp1 L=0.55u W=1u nf=1 m=1 model=pfet_06v0 spiceprefix=X}
C {devices/lab_pin.sym} 1150 170 0 0 {name=l21 lab=vprog}
C {devices/lab_pin.sym} 1110 200 0 0 {name=l22 lab=out}
C {devices/lab_pin.sym} 1150 230 0 0 {name=l23 lab=x1}
C {devices/lab_pin.sym} 1150 200 0 0 {name=l24 lab=vprog}
C {symbols/pfet_06v0.sym} 250 370 0 0 {name=Mp2 L=0.55u W=1u nf=1 m=1 model=pfet_06v0 spiceprefix=X}
C {devices/lab_pin.sym} 270 340 0 0 {name=l26 lab=vprog}
C {devices/lab_pin.sym} 230 370 0 0 {name=l27 lab=x1}
C {devices/lab_pin.sym} 270 400 0 0 {name=l28 lab=out}
C {devices/lab_pin.sym} 270 370 0 0 {name=l29 lab=vprog}
T {Level shifter 3.3V -> vprog (non-inverting): 3.3V inverter, nfet_06v0 pull-downs, cross-coupled pfet_06v0. Sizes are placeholders, not simulated.} 0 -60 0 0 0.3 0.3 {}
