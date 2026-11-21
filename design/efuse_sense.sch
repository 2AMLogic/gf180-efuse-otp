v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/iopin.sym} 0 40 0 0 {name=p0 lab=sbl}
C {devices/ipin.sym} 0 70 0 0 {name=p1 lab=sense_en}
C {devices/ipin.sym} 0 100 0 0 {name=p2 lab=clk}
C {devices/opin.sym} 0 130 0 0 {name=p3 lab=sense_out}
C {devices/iopin.sym} 0 160 0 0 {name=p4 lab=vdd33}
C {devices/iopin.sym} 0 190 0 0 {name=p5 lab=vprog}
C {devices/iopin.sym} 0 220 0 0 {name=p6 lab=vss}
C {symbols/pfet_03v3.sym} 250 200 0 0 {name=Mb L=1u W=4u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 270 170 0 0 {name=l1 lab=vdd33}
C {devices/lab_pin.sym} 230 200 0 0 {name=l2 lab=vbp}
C {devices/lab_pin.sym} 270 230 0 0 {name=l3 lab=vbp}
C {devices/lab_pin.sym} 270 200 0 0 {name=l4 lab=vdd33}
C {symbols/ppolyf_u.sym} 470 200 0 0 {name=Rb
W=1e-6
L=5.425e-6
model=ppolyf_u
spiceprefix=X
m=1}
C {devices/lab_pin.sym} 470 170 0 0 {name=l6 lab=vbp}
C {devices/lab_pin.sym} 470 230 0 0 {name=l7 lab=nb}
C {devices/lab_pin.sym} 450 200 0 0 {name=l5b lab=vss}
C {symbols/nfet_03v3.sym} 690 200 0 0 {name=Mbs L=0.28u W=2u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 710 170 0 0 {name=l9 lab=nb}
C {devices/lab_pin.sym} 670 200 0 0 {name=l10 lab=sense_en}
C {devices/lab_pin.sym} 710 230 0 0 {name=l11 lab=vss}
C {devices/lab_pin.sym} 710 200 0 0 {name=l12 lab=vss}
C {symbols/pfet_03v3.sym} 910 200 0 0 {name=Mbp L=0.28u W=1u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 930 170 0 0 {name=l14 lab=vdd33}
C {devices/lab_pin.sym} 890 200 0 0 {name=l15 lab=sense_en}
C {devices/lab_pin.sym} 930 230 0 0 {name=l16 lab=vbp}
C {devices/lab_pin.sym} 930 200 0 0 {name=l17 lab=vdd33}
C {symbols/pfet_03v3.sym} 1130 200 0 0 {name=Mf L=1u W=4u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 1150 170 0 0 {name=l19 lab=vdd33}
C {devices/lab_pin.sym} 1110 200 0 0 {name=l20 lab=vbp}
C {devices/lab_pin.sym} 1150 230 0 0 {name=l21 lab=sbl}
C {devices/lab_pin.sym} 1150 200 0 0 {name=l22 lab=vdd33}
C {symbols/pfet_03v3.sym} 250 370 0 0 {name=Mrf L=1u W=4u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 270 340 0 0 {name=l24 lab=vdd33}
C {devices/lab_pin.sym} 230 370 0 0 {name=l25 lab=vbp}
C {devices/lab_pin.sym} 270 400 0 0 {name=l26 lab=sref}
C {devices/lab_pin.sym} 270 370 0 0 {name=l27 lab=vdd33}
C {symbols/ppolyf_u.sym} 470 370 0 0 {name=Rref
W=1e-6
L=1.085e-6
model=ppolyf_u
spiceprefix=X
m=1}
C {devices/lab_pin.sym} 470 340 0 0 {name=l29 lab=sref}
C {devices/lab_pin.sym} 470 400 0 0 {name=l30 lab=rn1}
C {devices/lab_pin.sym} 450 370 0 0 {name=l28b lab=vss}
C {symbols/nfet_06v0.sym} 690 370 0 0 {name=Msw L=0.7u W=4u nf=1 m=1 model=nfet_06v0 spiceprefix=X}
C {devices/lab_pin.sym} 710 340 0 0 {name=l32 lab=rn1}
C {devices/lab_pin.sym} 670 370 0 0 {name=l33 lab=sense_en}
C {devices/lab_pin.sym} 710 400 0 0 {name=l34 lab=rn2}
C {devices/lab_pin.sym} 710 370 0 0 {name=l35 lab=vss}
C {symbols/nfet_06v0.sym} 910 370 0 0 {name=Msel L=0.7u W=60u nf=1 m=1 model=nfet_06v0 spiceprefix=X}
C {devices/lab_pin.sym} 930 340 0 0 {name=l37 lab=rn2}
C {devices/lab_pin.sym} 890 370 0 0 {name=l38 lab=vprog}
C {devices/lab_pin.sym} 930 400 0 0 {name=l39 lab=vss}
C {devices/lab_pin.sym} 930 370 0 0 {name=l40 lab=vss}
C {symbols/pfet_03v3.sym} 1130 370 0 0 {name=Mpca L=0.28u W=2u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 1150 340 0 0 {name=l42 lab=vdd33}
C {devices/lab_pin.sym} 1110 370 0 0 {name=l43 lab=clk}
C {devices/lab_pin.sym} 1150 400 0 0 {name=l44 lab=clkn}
C {devices/lab_pin.sym} 1150 370 0 0 {name=l45 lab=vdd33}
C {symbols/pfet_03v3.sym} 250 540 0 0 {name=Mpcb L=0.28u W=2u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 270 510 0 0 {name=l47 lab=vdd33}
C {devices/lab_pin.sym} 230 540 0 0 {name=l48 lab=sense_en}
C {devices/lab_pin.sym} 270 570 0 0 {name=l49 lab=clkn}
C {devices/lab_pin.sym} 270 540 0 0 {name=l50 lab=vdd33}
C {symbols/nfet_03v3.sym} 470 540 0 0 {name=Mnca L=0.28u W=2u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 490 510 0 0 {name=l52 lab=clkn}
C {devices/lab_pin.sym} 450 540 0 0 {name=l53 lab=clk}
C {devices/lab_pin.sym} 490 570 0 0 {name=l54 lab=mc}
C {devices/lab_pin.sym} 490 540 0 0 {name=l55 lab=vss}
C {symbols/nfet_03v3.sym} 690 540 0 0 {name=Mncb L=0.28u W=2u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 710 510 0 0 {name=l57 lab=mc}
C {devices/lab_pin.sym} 670 540 0 0 {name=l58 lab=sense_en}
C {devices/lab_pin.sym} 710 570 0 0 {name=l59 lab=vss}
C {devices/lab_pin.sym} 710 540 0 0 {name=l60 lab=vss}
C {efuse_comp.sym} 910 540 0 0 {name=Xcmp}
C {devices/lab_pin.sym} 830 540 0 0 {name=l62 lab=sref}
C {devices/lab_pin.sym} 830 560 0 0 {name=l63 lab=sbl}
C {devices/lab_pin.sym} 830 580 0 0 {name=l64 lab=clkn}
C {devices/lab_pin.sym} 830 600 0 0 {name=l65 lab=cp}
C {devices/lab_pin.sym} 830 620 0 0 {name=l66 lab=cn}
C {devices/lab_pin.sym} 830 640 0 0 {name=l67 lab=vdd33}
C {devices/lab_pin.sym} 830 660 0 0 {name=l68 lab=vss}
C {symbols/pfet_03v3.sym} 1130 540 0 0 {name=Mpqa L=0.28u W=4u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 1150 510 0 0 {name=l70 lab=vdd33}
C {devices/lab_pin.sym} 1110 540 0 0 {name=l71 lab=cn}
C {devices/lab_pin.sym} 1150 570 0 0 {name=l72 lab=mq}
C {devices/lab_pin.sym} 1150 540 0 0 {name=l73 lab=vdd33}
C {symbols/pfet_03v3.sym} 250 710 0 0 {name=Mpqb L=0.28u W=4u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 270 680 0 0 {name=l75 lab=mq}
C {devices/lab_pin.sym} 230 710 0 0 {name=l76 lab=qb}
C {devices/lab_pin.sym} 270 740 0 0 {name=l77 lab=sense_out}
C {devices/lab_pin.sym} 270 710 0 0 {name=l78 lab=vdd33}
C {symbols/nfet_03v3.sym} 470 710 0 0 {name=Mnqa L=0.28u W=1u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 490 680 0 0 {name=l80 lab=sense_out}
C {devices/lab_pin.sym} 450 710 0 0 {name=l81 lab=cn}
C {devices/lab_pin.sym} 490 740 0 0 {name=l82 lab=vss}
C {devices/lab_pin.sym} 490 710 0 0 {name=l83 lab=vss}
C {symbols/nfet_03v3.sym} 690 710 0 0 {name=Mnqb L=0.28u W=1u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 710 680 0 0 {name=l85 lab=sense_out}
C {devices/lab_pin.sym} 670 710 0 0 {name=l86 lab=qb}
C {devices/lab_pin.sym} 710 740 0 0 {name=l87 lab=vss}
C {devices/lab_pin.sym} 710 710 0 0 {name=l88 lab=vss}
C {symbols/pfet_03v3.sym} 910 710 0 0 {name=Mpba L=0.28u W=4u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 930 680 0 0 {name=l90 lab=vdd33}
C {devices/lab_pin.sym} 890 710 0 0 {name=l91 lab=cp}
C {devices/lab_pin.sym} 930 740 0 0 {name=l92 lab=mb}
C {devices/lab_pin.sym} 930 710 0 0 {name=l93 lab=vdd33}
C {symbols/pfet_03v3.sym} 1130 710 0 0 {name=Mpbb L=0.28u W=4u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 1150 680 0 0 {name=l95 lab=mb}
C {devices/lab_pin.sym} 1110 710 0 0 {name=l96 lab=sense_out}
C {devices/lab_pin.sym} 1150 740 0 0 {name=l97 lab=qb}
C {devices/lab_pin.sym} 1150 710 0 0 {name=l98 lab=vdd33}
C {symbols/nfet_03v3.sym} 250 880 0 0 {name=Mnba L=0.28u W=1u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 270 850 0 0 {name=l100 lab=qb}
C {devices/lab_pin.sym} 230 880 0 0 {name=l101 lab=cp}
C {devices/lab_pin.sym} 270 910 0 0 {name=l102 lab=vss}
C {devices/lab_pin.sym} 270 880 0 0 {name=l103 lab=vss}
C {symbols/nfet_03v3.sym} 470 880 0 0 {name=Mnbb L=0.28u W=1u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 490 850 0 0 {name=l105 lab=qb}
C {devices/lab_pin.sym} 450 880 0 0 {name=l106 lab=sense_out}
C {devices/lab_pin.sym} 490 910 0 0 {name=l107 lab=vss}
C {devices/lab_pin.sym} 490 880 0 0 {name=l108 lab=vss}
T {Sense path: equal bias currents (pfet_03v3 mirror) into the selected-fuse bus sbl and a 400 ohm reference (A6, decision 0003) behind a dummy switch+select; clocked comparator; NOR SR latch holds sense_out (1 = programmed). Rb and Rref are PDK ppolyf_u resistors (r_width 1 um, r_length solved so the model's nominal R is 2k / 400 ohm; drawn geometry is what LVS compares). Sizes are placeholders, not simulated.} 0 -60 0 0 0.3 0.3 {}
