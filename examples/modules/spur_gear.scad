// @mps id=org.mechstudio.sample.spur-gear version=1.0.0 name="Spur Gear" description="Independent module exercising dimensional, count, angle, enum, ratio, and boolean parameters"

/* [Gear geometry] */
// @mps-param type=length label="Module" description="Tooth module in the selected dimensional input system"
tooth_module = 2; // [0.1:0.1:20]

// @mps-param type=integer label="Tooth count" description="Number of teeth"
tooth_count = 20; // [6:1:200]

// @mps-param type=length label="Thickness"
thickness = 8; // [0.1:0.1:100]

// @mps-param type=length label="Bore diameter"
bore_diameter = 5; // [0:0.1:200]

// @mps-param type=angle label="Pressure angle"
pressure_angle = 20; // [14.5:0.5:30]

/* [Options] */
// @mps-param type=enum label="Hub style"
hub_style = "none"; // [none:No hub, one:One side, both:Both sides]

// @mps-param type=length label="Hub diameter" visible_if="hub_style=one"
hub_diameter = 20; // [0:0.1:300]

// @mps-param type=boolean label="Lightening holes"
lightening_holes = false;

// @mps-param type=ratio label="Root clearance ratio"
clearance_ratio = 0.25; // [0:0.01:1]

/* [Hidden] */
$fn = 96;

pitch_diameter = tooth_module * tooth_count;
root_diameter = max(tooth_module * 2, pitch_diameter - 2.5 * tooth_module);
outside_diameter = pitch_diameter + 2 * tooth_module;
tooth_depth = (outside_diameter - root_diameter) / 2;
tooth_width = PI * tooth_module * 0.46;

assert(tooth_module > 0, "Module must be positive");
assert(tooth_count >= 6, "At least six teeth are required");
assert(thickness > 0, "Thickness must be positive");
assert(bore_diameter >= 0 && bore_diameter < root_diameter, "Bore must fit within the root diameter");

module gear_body() {
    union() {
        cylinder(d=root_diameter, h=thickness);
        for (index = [0:tooth_count-1])
            rotate([0, 0, index * 360 / tooth_count])
                translate([root_diameter / 2 - 0.01, -tooth_width / 2, 0])
                    cube([tooth_depth + 0.02, tooth_width, thickness]);
        if (hub_style == "one" || hub_style == "both")
            cylinder(d=hub_diameter, h=thickness + tooth_module);
        if (hub_style == "both")
            translate([0, 0, -tooth_module]) cylinder(d=hub_diameter, h=tooth_module);
    }
}

difference() {
    gear_body();
    translate([0, 0, -tooth_module - 0.01])
        cylinder(d=bore_diameter, h=thickness + 2 * tooth_module + 0.02);
    if (lightening_holes)
        for (index = [0:5])
            rotate([0, 0, index * 60])
                translate([pitch_diameter * 0.28, 0, -0.01])
                    cylinder(d=max(tooth_module, pitch_diameter * 0.12), h=thickness + 0.02);
}

