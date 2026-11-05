v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/ipin.sym} 0 40 0 0 {name=p0 lab=inp}
C {devices/ipin.sym} 0 70 0 0 {name=p1 lab=inn}
C {devices/ipin.sym} 0 100 0 0 {name=p2 lab=clkn}
C {devices/opin.sym} 0 130 0 0 {name=p3 lab=outp}
C {devices/opin.sym} 0 160 0 0 {name=p4 lab=outn}
C {devices/iopin.sym} 0 190 0 0 {name=p5 lab=vdd33}
C {devices/iopin.sym} 0 220 0 0 {name=p6 lab=vss}
C {symbols/pfet_03v3.sym} 250 200 0 0 {name=Mt L=0.28u W=8u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 270 170 0 0 {name=l1 lab=vdd33}
C {devices/lab_pin.sym} 230 200 0 0 {name=l2 lab=clkn}
C {devices/lab_pin.sym} 270 230 0 0 {name=l3 lab=tail}
C {devices/lab_pin.sym} 270 200 0 0 {name=l4 lab=vdd33}
C {symbols/pfet_03v3.sym} 470 200 0 0 {name=M1 L=2.24u W=8u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 490 170 0 0 {name=l6 lab=tail}
C {devices/lab_pin.sym} 450 200 0 0 {name=l7 lab=inp}
C {devices/lab_pin.sym} 490 230 0 0 {name=l8 lab=outp}
C {devices/lab_pin.sym} 490 200 0 0 {name=l9 lab=vdd33}
C {symbols/pfet_03v3.sym} 690 200 0 0 {name=M2 L=2.24u W=8u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 710 170 0 0 {name=l11 lab=tail}
C {devices/lab_pin.sym} 670 200 0 0 {name=l12 lab=inn}
C {devices/lab_pin.sym} 710 230 0 0 {name=l13 lab=outn}
C {devices/lab_pin.sym} 710 200 0 0 {name=l14 lab=vdd33}
C {symbols/nfet_03v3.sym} 910 200 0 0 {name=Mx1 L=0.28u W=8u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 930 170 0 0 {name=l16 lab=outp}
C {devices/lab_pin.sym} 890 200 0 0 {name=l17 lab=outn}
C {devices/lab_pin.sym} 930 230 0 0 {name=l18 lab=vss}
C {devices/lab_pin.sym} 930 200 0 0 {name=l19 lab=vss}
C {symbols/nfet_03v3.sym} 1130 200 0 0 {name=Mx2 L=0.28u W=8u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 1150 170 0 0 {name=l21 lab=outn}
C {devices/lab_pin.sym} 1110 200 0 0 {name=l22 lab=outp}
C {devices/lab_pin.sym} 1150 230 0 0 {name=l23 lab=vss}
C {devices/lab_pin.sym} 1150 200 0 0 {name=l24 lab=vss}
C {symbols/nfet_03v3.sym} 250 370 0 0 {name=Mr1 L=0.28u W=1u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 270 340 0 0 {name=l26 lab=outp}
C {devices/lab_pin.sym} 230 370 0 0 {name=l27 lab=clkn}
C {devices/lab_pin.sym} 270 400 0 0 {name=l28 lab=vss}
C {devices/lab_pin.sym} 270 370 0 0 {name=l29 lab=vss}
C {symbols/nfet_03v3.sym} 470 370 0 0 {name=Mr2 L=0.28u W=1u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 490 340 0 0 {name=l31 lab=outn}
C {devices/lab_pin.sym} 450 370 0 0 {name=l32 lab=clkn}
C {devices/lab_pin.sym} 490 400 0 0 {name=l33 lab=vss}
C {devices/lab_pin.sym} 490 370 0 0 {name=l34 lab=vss}
T {Clocked comparator, PMOS input pair (inputs sit near vss), NMOS cross-coupled latch. clkn high = reset (outputs low); clkn low = evaluate; outp high when inp < inn. Input pair 8u/2.24u (32x the gate area of 2u/0.28u, ~5.7x lower mismatch offset, same W/L as 4u/1.12u, and weaker than the 8u latch so it regenerates; issue 77); other sizes placeholder.} 0 -60 0 0 0.3 0.3 {}
