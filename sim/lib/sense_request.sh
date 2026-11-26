#!/usr/bin/env bash
# Deck and klt request shared by the deterministic sense sweeps.
# Source after pdk_env.sh. The runners use the same times in their summaries.
# shellcheck disable=SC2034  # Both runners record the clock edge in their summaries.
T_EDGE=15n
T_PRE=14.9n  # margin read, just before the edge
T_OUT=38n    # latched sense_out read

# The physical reference keeps XRref. The ideal sweep replaces it with a plain
# resistor. Both retain the PDK bias resistor XRb, so every MOS corner needs a
# resistor section. The PDK has no fs/sf resistor section, so use typical for both (A8).
# sense_request <stem> <rfuse|open> <rref|phys> [margin sign]
# Write the deck and request in $rec and append the request path to reqs.
# The margin bench grades programmed (+1) and intact/control (-1) reads.
sense_request() {
  local stem="$1" rf="$2" rr="$3" sgn="${4:-}"
  local deck="${rec:?}/$stem.cir" template="${repo:?}/sim/sense-margin/sense.cir.in"
  local rref_line='^XRref rn1 sref vss ppolyf_u r_width=1.05e-6 r_length=0.8e-6 m=1$'
  [[ "$rf" == open ]] && rf=1G
  { sed -e "s#@DESIGN@#$PDK_FLEET_LIB_DIR/design.ngspice#" -e "s#@RFUSE@#$rf#" "$template"
    echo
    if [[ "$rr" == phys ]]; then      # keep the committed ppolyf_u XRref
      sub efuse_sense
    else
      sub efuse_sense | sed -e "s#$rref_line#Rref rn1 sref $rr#"
    fi
    echo
    sub efuse_comp
  } > "$deck"
  if [[ "$rr" == phys ]]; then
    grep -q "^XRref rn1 sref vss ppolyf_u " "$deck" || { echo "run.sh: physical XRref not found in efuse_sense" >&2; exit 1; }
  else
    grep -q "^Rref rn1 sref $rr\$" "$deck" || { echo "run.sh: Rref line not found in efuse_sense" >&2; exit 1; }
  fi
  jq -n --arg net "$stem.cir" --arg lib "libs.tech/ngspice/sm141064.ngspice" \
        --arg tpre "$T_PRE" --arg tout "$T_OUT" --arg sgn "$sgn" \
        --argjson pvt_proc "$PVT_PROCESSES" --argjson pvt_temp "$PVT_TEMPERATURES_C" \
        --argjson pvt_3v3 "$PVT_SUPPLY_3V3" '
    {netlist:$net, engine:"ngspice",
     models:{lib:$lib, pdk:"gf180mcuD"},
     corners:{process:($pvt_proc|map({name:.,
              sections:[., ({"typical":"res_typical","ss":"res_ss","ff":"res_ff"}[.] // "res_typical"), "mimcap_typical"]})),
              supply_v:{vdd33:$pvt_3v3}, temperature_c:$pvt_temp},
     analysis:{kind:"tran", args:"20p 40n"},  # 100p under-resolves the 200p edge: decisions flipped with the step (issue 77)
     measurements:[
       (select($sgn != "") | {name:"margin_v", spice:(".meas tran margin_v find par(\u0027" + $sgn + "*(v(sbl)-v(xsa.sref))\u0027) at=" + $tpre), unit:"V", limits:{min:0}}),
       {name:"v_sbl", spice:(".meas tran v_sbl find v(sbl) at=" + $tpre), unit:"V"},
       {name:"v_sref", spice:(".meas tran v_sref find v(xsa.sref) at=" + $tpre), unit:"V"},
       {name:"v_sense_out", spice:(".meas tran v_sense_out find v(sense_out) at=" + $tout), unit:"V"},
       {name:"v_cp", spice:(".meas tran v_cp find v(xsa.cp) at=" + $tout), unit:"V"},
       {name:"v_cn", spice:(".meas tran v_cn find v(xsa.cn) at=" + $tout), unit:"V"},
       (select($sgn != "") | {name:"v_vdd33", spice:(".meas tran v_vdd33 find v(vdd33) at=" + $tout), unit:"V"})],
     options:{timeout_s:60, ngspice_init:["set measureprec=9"]}}' > "$rec/$stem.json"
  reqs+=("$rec/$stem.json")
}
