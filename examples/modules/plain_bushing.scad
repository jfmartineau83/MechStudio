// @mps id=org.mechstudio.sample.plain-bushing version=1.0.0 name="Plain Bushing" description="Simple cylindrical sleeve used to verify the module contract"

/* [Dimensions] */
// @mps-param type=length label="Inner diameter" description="Diameter of the through bore"
inner_diameter = 8; // [0.1:0.1:500]

// @mps-param type=length label="Outer diameter" description="Outside finished diameter"
outer_diameter = 12; // [0.1:0.1:500]

// @mps-param type=length label="Length" description="Overall axial length"
length = 20; // [0.1:0.1:1000]

/* [Hidden] */
$fn = 128;

assert(inner_diameter > 0, "Inner diameter must be positive");
assert(outer_diameter > 0, "Outer diameter must be positive");
assert(length > 0, "Length must be positive");
assert(outer_diameter > inner_diameter, "Outer diameter must exceed inner diameter");

difference() {
    cylinder(d=outer_diameter, h=length);
    translate([0, 0, -0.01]) cylinder(d=inner_diameter, h=length + 0.02);
}

