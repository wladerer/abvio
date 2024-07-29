# Specification of Structural Parameters

Currently, this is a relatively primitive implementation. 

## Options

The following outlines options to specify the structure that will be used in your VASP calculation.

___


Option     | **Arguments/Options**        | Datatype | Required
---        |    ---                       | ---      | ---
mode       | external     \| internal     | `str`    | true
cell       | primitive    \| conventional | `str`    | false
symmetrize | true         \| false        | `bool`   | false
fractional | true         \| false        | `bool`   | false 
lattice    | `lattice array` \| `lattice params` | `array` \| `list` | false
file       | `file path`     | `str`                 | false
string     | `poscar string` | `str`                 | false
coords     | `coordinates`   | `array`               | false
species    | `species`       | `list[str]`           | false
code       | `mp-code`       | `str`                 | false
prototype  | `name: basis vector`| `dict`            | false
scale      | `scale`         | `int`                 | false


## Structure creation modes

Abvio attempts to reduce the amount of typing one must do in order to get a calculation going. Unfortunately, this means that sometimes required tags must be used to simplify the parsing of the file. Specifically, I am referring to the `mode` tag. This is a feature unique, I assume, to abvio. This tells abvio if you will be getting the structure from an external source (a file, materials project, or a poscar string), specifying the structure manually (species, coordinates, and lattice), or generating a structure from a well known crystal type.  

We can summarize the `mode`s in the following table

Mode     | Requires        
---      |    ---                  
external | file \| string \| code
internal | species, lattice, coords \| species, prototype  

## Notes

The following section expands upon `poscar` options.

#### lattice

This parameter might be the most confusing, so I put it first so it is not glanced over. You may explicity specify the lattice as an array or as a list of lattice parameters. For example, the same fluorite structure can be created using either

```yaml
poscar:
    mode: internal
    species: [Cs, F, F]
    lattice:
        a: 5.52
        b: 5.52
        c: 5.52
        alpha: 90.0
        beta: 90.0
        gamma: 90.0
    coords: [
        [0.    0.    0.   ]
        [0.    2.758 2.758]
        [2.758 0.    2.758]
        [2.758 2.758 0.   ]
        [1.379 4.137 1.379]
        [1.379 4.137 4.137]
        [1.379 1.379 4.137]
        [1.379 1.379 1.379]
        [4.137 4.137 4.137]
        [4.137 4.137 1.379]
        [4.137 1.379 1.379]
        [4.137 1.379 4.137]
    ]
```

Or you can do this

```yaml
poscar:
    mode: internal
    species: [Cs, F, F]
    lattice: [
        [5.516052 0.000000 0.000000],
        [0.000000 5.516052 0.000000],
        [0.000000 0.000000 5.516052],
    ]
    coords: [
        [0.    0.    0.   ]
        [0.    2.758 2.758]
        [2.758 0.    2.758]
        [2.758 2.758 0.   ]
        [1.379 4.137 1.379]
        [1.379 4.137 4.137]
        [1.379 1.379 4.137]
        [1.379 1.379 1.379]
        [4.137 4.137 4.137]
        [4.137 4.137 1.379]
        [4.137 1.379 1.379]
        [4.137 1.379 4.137]
    ]
```


#### code

You may pull a structure directly from the materials project database. The cell setting can be optionally specified to either primitive or conventional. Additionally, you can have the structure automatically symmetrized if you wish. These options are false by default.

!!! Note

    Make sure your [MP_API_KEY](https://next-gen.materialsproject.org/api) environment variable is set 


#### file

Structures can be read in from any file supported by [pymatgen](https://pymatgen.org/pymatgen.io.html) io methods. To do this, you must give either the absolute path of the file or the relative path with respect to where you are running the `abvio` commands. 

```yaml
poscar:
    file: /home/users/me/Downloads/NiO.cif
```

#### fractional 

Explicitly defined coordinates are assumed to be both read in and written as cartesian by default. You may use this setting to inform abvio that you wish to set this behavior as fractional instead. 


#### string

You may use the multiline string feature of the yaml file format to explicitly write out the POSCAR in your input file. 

#### prototype

You may create a structure by specifying the prototypical structure type, list of species corresponding to symmetrically distinct sites, and minimally required lattice parameters. For example, CaTiO3 can be specified using the following `poscar` input parameters

```yaml
poscar:
    prototype: 
        - perovskite: 3.89
    species: [Ca, Ti, O]
```

Where `prototype` takes the name and the associated lattice parameter

##### Supported Keys


Prototype     | Space Group      
---           |    ---                
fcc           | Fm-3m          
bcc           | Im-3m          
hcp           | P6_3/mmc       
diamond       | Fd-3m          
rocksalt      | Fm-3m          
perovskite    | Pm-3m          
cscl          | Pm-3m          
fluorite      | Fm-3m          
antifluorite  | Fm-3m          
zincblende    | F-43m          


#### scale

You may adjust the scaling parameter of your basis vectors. Often, this is useful for arbitrarily adjusting the volume of your cell or lazily creating cubic/tetragonal systems. 
