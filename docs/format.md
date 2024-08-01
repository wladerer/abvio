# abvio input files and yaml

This section will give an overview of both the yaml format and the abvio input file format

## yaml

Yaml is a file format designed to be human readable but easily parsed by software. This is achieved by strcturing everything as `key:value` pairs. In practice, this just means that everything in the file has a label and we can access those things by referencing the labels by calling its name. For example, if I wanted to refer to look up the "mythical creatures" section of the following file

```yaml
mythical creatures:
    - sasquatch:
        age: 1032
        diet: poutine
        power: is blurry
        location: Wisconsin, USA
    - lochness monster:
        age: false
        diet: horses
        power: shapeshifts into driftwood
        location: Lake Wakatipu, NZ
suspicious:
    sto3g: true
    ano-rcc-vtz: true
    clebcsh-gordan: false
pauli-matrix:
    - [ 1, 0]
    - [ 0,-1]
pauli-matrices:
    - [[0, 1],
       [1, 0]]
    - [[0, -i],
       [i,  0]]
```

I would get back a list of two dictionaries: `sasquatch` and `lochness monster` that contains more key value pairs about each creature.

To our benefit, and our detriment, there is some flexibility in the way we can represent the same things. You will notice that in the `pauli-matrix` entry we write out a matrix as a list of lists using a `-` next to each row of the matrix. Whereas, `pauli-matrices` is a list of lists of lists (aka a list of matrices). This will be an important distinction if you are writing coordinates, lattices, or band structure paths manually. 


## abvio yaml

There are only a few "rules" when it comes to abvio. 

#### structure, incar, and kpoints must be in the highest scope of the file

Unfortunately, the difference is hard to see, but "scope" or hierarchy is distinguished by indentation. The following is a valid abvio yaml file

> Good: 
>```yaml
> structure:
>    ...
> kpoints:
>    spacing: 800
>    mode: spacing
> incar:
>   ...
> ```

Where this one is not

> Bad: 
>```yaml
> structure:
>    ...
>   kpoints:
>       spacing: 800
>       mode: spacing
> incar:
>   ...
> ```

Thankfully, abvio will let you know it is missing "kpoints" when you try to write the VASP input files.

#### structure and kpoints must always have a mode tag

abvio requires a "mode" tag to handle the many options of creating structures and kpoint meshes. You can find all of these features listed further down in the documentation. 

#### ranges requires a start, stop, and value

when assigning site properties like `MAGMOM` and `LDAUU`, there is a 'range' option. This is detected automatically (therefore no need to add `mode`), but will need to explicitly state the start, stop, and value of the site property in the following way

```yaml
incar:
    ispin: 2
    magmom:
        - {start: 0, stop: 12, value: 3.4}
```

Where the above example would apply a magnetic moment of 3.4 to the first twelve atoms in your structure. We can also apply "step" to this logic as well, where the following range would apply alternating values of [Sx = 0, Sy = 0, Sz=1] and [Sx = 0, Sy = 0, Sz=-1]

```yaml
incar:
    lsorbit: true
    magmom:
        - {start: 0, stop: 12, step: 2, value: [0, 0, 1]}
        - {start: 1, stop: 12, step: 2, value: [0, 0, -1]}
```

Which might come in handy if you are trying to create a spin-orbit coupled antiferromagnet. 



## section specific rules


### structure

structure tries to be as flexible as possible, including allowing the user to simply just provide a path to a file if they so choose. 


mode      |  Expect Inputs(s) | Notes
---       |    ---     | ---
external  |  file \| string \| code | code must be in the format mp-...
manual    |  species, lattice, coords | lattice can be an array or a dictionary
prototype |  protoype, lattice | at least one lattice constant is required



### kpoints

kpoints is less flexible and is honestly the least well implemented feature at the moment. `spacing` must always be specified, regardless of the mode. The user must be aware that spacing can refer to kpoint mesh density per volume, unit length, or path. This might be confusing at first. I will put this in a warning box just so it's extra clear

!!! danger

    `spacing` keyword can refer to kpoint mesh density per volume, unit length, or path


mode      |  Spacing format           | Notes
---       |    ---                    | ---
gamma     | list | traditional [kx, ky, kz] or explicit
monkhorst | list | you can misspell this one (same as gamma)
line      |  list  | only need to specify a point on a path once
autoline  | integer | will generate labels and paths for you
surface   |  integer                  | must be quite high for fermi surfaces (800+)
