v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/ipin.sym} 0 40 0 0 {name=p0 lab=col_sel}
C {devices/ipin.sym} 0 70 0 0 {name=p1 lab=prog_strobe}
C {devices/ipin.sym} 0 100 0 0 {name=p2 lab=sense_en}
C {devices/iopin.sym} 0 130 0 0 {name=p3 lab=bl}
C {devices/iopin.sym} 0 160 0 0 {name=p4 lab=sbl}
C {devices/iopin.sym} 0 190 0 0 {name=p5 lab=vdd33}
C {devices/iopin.sym} 0 220 0 0 {name=p6 lab=vprog}
C {devices/iopin.sym} 0 250 0 0 {name=p7 lab=vss}
C {symbols/pfet_03v3.sym} 250 200 0 0 {name=Mppa L=0.28u W=2u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 270 170 0 0 {name=l1 lab=vdd33}
C {devices/lab_pin.sym} 230 200 0 0 {name=l2 lab=col_sel}
C {devices/lab_pin.sym} 270 230 0 0 {name=l3 lab=npg}
C {devices/lab_pin.sym} 270 200 0 0 {name=l4 lab=vdd33}
C {symbols/pfet_03v3.sym} 470 200 0 0 {name=Mppb L=0.28u W=2u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 490 170 0 0 {name=l6 lab=vdd33}
C {devices/lab_pin.sym} 450 200 0 0 {name=l7 lab=prog_strobe}
C {devices/lab_pin.sym} 490 230 0 0 {name=l8 lab=npg}
C {devices/lab_pin.sym} 490 200 0 0 {name=l9 lab=vdd33}
C {symbols/nfet_03v3.sym} 690 200 0 0 {name=Mnpa L=0.28u W=2u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 710 170 0 0 {name=l11 lab=npg}
C {devices/lab_pin.sym} 670 200 0 0 {name=l12 lab=col_sel}
C {devices/lab_pin.sym} 710 230 0 0 {name=l13 lab=mp}
C {devices/lab_pin.sym} 710 200 0 0 {name=l14 lab=vss}
C {symbols/nfet_03v3.sym} 910 200 0 0 {name=Mnpb L=0.28u W=2u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 930 170 0 0 {name=l16 lab=mp}
C {devices/lab_pin.sym} 890 200 0 0 {name=l17 lab=prog_strobe}
C {devices/lab_pin.sym} 930 230 0 0 {name=l18 lab=vss}
C {devices/lab_pin.sym} 930 200 0 0 {name=l19 lab=vss}
C {efuse_ls.sym} 1130 200 0 0 {name=Xls}
C {devices/lab_pin.sym} 1050 200 0 0 {name=l21 lab=npg}
C {devices/lab_pin.sym} 1050 220 0 0 {name=l22 lab=pg}
C {devices/lab_pin.sym} 1050 240 0 0 {name=l23 lab=vdd33}
C {devices/lab_pin.sym} 1050 260 0 0 {name=l24 lab=vprog}
C {devices/lab_pin.sym} 1050 280 0 0 {name=l25 lab=vss}
C {symbols/pfet_06v0.sym} 250 370 0 0 {name=Mdrv L=0.55u W=100u nf=1 m=3 model=pfet_06v0 spiceprefix=X}
C {devices/lab_pin.sym} 270 340 0 0 {name=l27 lab=vprog}
C {devices/lab_pin.sym} 230 370 0 0 {name=l28 lab=pg}
C {devices/lab_pin.sym} 270 400 0 0 {name=l29 lab=bl}
C {devices/lab_pin.sym} 270 370 0 0 {name=l30 lab=vprog}
C {symbols/pfet_03v3.sym} 470 370 0 0 {name=Mpra L=0.28u W=2u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 490 340 0 0 {name=l32 lab=vdd33}
C {devices/lab_pin.sym} 450 370 0 0 {name=l33 lab=col_sel}
C {devices/lab_pin.sym} 490 400 0 0 {name=l34 lab=nrd}
C {devices/lab_pin.sym} 490 370 0 0 {name=l35 lab=vdd33}
C {symbols/pfet_03v3.sym} 690 370 0 0 {name=Mprb L=0.28u W=2u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 710 340 0 0 {name=l37 lab=vdd33}
C {devices/lab_pin.sym} 670 370 0 0 {name=l38 lab=sense_en}
C {devices/lab_pin.sym} 710 400 0 0 {name=l39 lab=nrd}
C {devices/lab_pin.sym} 710 370 0 0 {name=l40 lab=vdd33}
C {symbols/nfet_03v3.sym} 910 370 0 0 {name=Mnra L=0.28u W=2u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 930 340 0 0 {name=l42 lab=nrd}
C {devices/lab_pin.sym} 890 370 0 0 {name=l43 lab=col_sel}
C {devices/lab_pin.sym} 930 400 0 0 {name=l44 lab=mr}
C {devices/lab_pin.sym} 930 370 0 0 {name=l45 lab=vss}
C {symbols/nfet_03v3.sym} 1130 370 0 0 {name=Mnrb L=0.28u W=2u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 1150 340 0 0 {name=l47 lab=mr}
C {devices/lab_pin.sym} 1110 370 0 0 {name=l48 lab=sense_en}
C {devices/lab_pin.sym} 1150 400 0 0 {name=l49 lab=vss}
C {devices/lab_pin.sym} 1150 370 0 0 {name=l50 lab=vss}
C {symbols/pfet_03v3.sym} 250 540 0 0 {name=Mpr L=0.28u W=2u nf=1 m=1 model=pfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 270 510 0 0 {name=l52 lab=vdd33}
C {devices/lab_pin.sym} 230 540 0 0 {name=l53 lab=nrd}
C {devices/lab_pin.sym} 270 570 0 0 {name=l54 lab=rd}
C {devices/lab_pin.sym} 270 540 0 0 {name=l55 lab=vdd33}
C {symbols/nfet_03v3.sym} 470 540 0 0 {name=Mnr L=0.28u W=1u nf=1 m=1 model=nfet_03v3 spiceprefix=X}
C {devices/lab_pin.sym} 490 510 0 0 {name=l57 lab=rd}
C {devices/lab_pin.sym} 450 540 0 0 {name=l58 lab=nrd}
C {devices/lab_pin.sym} 490 570 0 0 {name=l59 lab=vss}
C {devices/lab_pin.sym} 490 540 0 0 {name=l60 lab=vss}
C {symbols/nfet_06v0.sym} 690 540 0 0 {name=Mrs L=0.7u W=4u nf=1 m=1 model=nfet_06v0 spiceprefix=X}
C {devices/lab_pin.sym} 710 510 0 0 {name=l62 lab=bl}
C {devices/lab_pin.sym} 670 540 0 0 {name=l63 lab=rd}
C {devices/lab_pin.sym} 710 570 0 0 {name=l64 lab=sbl}
C {devices/lab_pin.sym} 710 540 0 0 {name=l65 lab=vss}
T {Column driver: pg = LS(NAND(col_sel,prog_strobe)) gates a pfet_06v0 from vprog to bl (low = program); read switch nfet_06v0 bl-sbl gated by col_sel AND sense_en. Sizes are placeholders, not simulated.} 0 -60 0 0 0.3 0.3 {}
