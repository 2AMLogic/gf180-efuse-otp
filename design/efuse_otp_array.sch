v {xschem version=3.4.7 file_version=1.2}
G {}
K {}
V {}
S {}
E {}
C {devices/ipin.sym} 0 40 0 0 {name=p0 lab=row_sel[31:0]}
C {devices/ipin.sym} 0 70 0 0 {name=p1 lab=col_sel[7:0]}
C {devices/ipin.sym} 0 100 0 0 {name=p2 lab=prog_strobe}
C {devices/ipin.sym} 0 130 0 0 {name=p3 lab=sense_en}
C {devices/ipin.sym} 0 160 0 0 {name=p4 lab=clk}
C {devices/opin.sym} 0 190 0 0 {name=p5 lab=sense_out}
C {devices/iopin.sym} 0 220 0 0 {name=p6 lab=vdd33}
C {devices/iopin.sym} 0 250 0 0 {name=p7 lab=vprog}
C {devices/iopin.sym} 0 280 0 0 {name=p8 lab=vss}
C {efuse_rowdrv.sym} 250 200 0 0 {name=Xrd[31:0]}
C {devices/lab_pin.sym} 170 200 0 0 {name=l1 lab=row_sel[31:0]}
C {devices/lab_pin.sym} 170 220 0 0 {name=l2 lab=wl[31:0]}
C {devices/lab_pin.sym} 170 240 0 0 {name=l3 lab=vdd33}
C {devices/lab_pin.sym} 170 260 0 0 {name=l4 lab=vprog}
C {devices/lab_pin.sym} 170 280 0 0 {name=l5 lab=vss}
C {efuse_coldrv.sym} 470 200 0 0 {name=Xcd[7:0]}
C {devices/lab_pin.sym} 390 200 0 0 {name=l7 lab=col_sel[7:0]}
C {devices/lab_pin.sym} 390 220 0 0 {name=l8 lab=prog_strobe}
C {devices/lab_pin.sym} 390 240 0 0 {name=l9 lab=sense_en}
C {devices/lab_pin.sym} 390 260 0 0 {name=l10 lab=bl[7:0]}
C {devices/lab_pin.sym} 390 280 0 0 {name=l11 lab=sbl}
C {devices/lab_pin.sym} 390 300 0 0 {name=l12 lab=vdd33}
C {devices/lab_pin.sym} 390 320 0 0 {name=l13 lab=vprog}
C {devices/lab_pin.sym} 390 340 0 0 {name=l14 lab=vss}
C {efuse_row.sym} 690 200 0 0 {name=Xarr[31:0]}
C {devices/lab_pin.sym} 610 200 0 0 {name=l16 lab=bl[7:0]}
C {devices/lab_pin.sym} 610 220 0 0 {name=l17 lab=wl[31:0]}
C {devices/lab_pin.sym} 610 240 0 0 {name=l18 lab=vss}
C {efuse_sense.sym} 910 200 0 0 {name=Xsa}
C {devices/lab_pin.sym} 830 200 0 0 {name=l20 lab=sbl}
C {devices/lab_pin.sym} 830 220 0 0 {name=l21 lab=sense_en}
C {devices/lab_pin.sym} 830 240 0 0 {name=l22 lab=clk}
C {devices/lab_pin.sym} 830 260 0 0 {name=l23 lab=sense_out}
C {devices/lab_pin.sym} 830 280 0 0 {name=l24 lab=vdd33}
C {devices/lab_pin.sym} 830 300 0 0 {name=l25 lab=vprog}
C {devices/lab_pin.sym} 830 320 0 0 {name=l26 lab=vss}
T {Array top, 32 rows x 8 columns (decision 0001): bit address = row*8 + col. Row drivers, column drivers, 256 bitcells, one sense path.} 0 -60 0 0 0.3 0.3 {}
