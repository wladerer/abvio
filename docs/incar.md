# Specification of Incar Parameters

Specifiication of the INCAR parameters is nearly identical to how you would normally create an INCAR. Some differences include:

- magnetic moments, selective dynamics, and U-corrections can be specified in several simpler conventions
- automatic detection (and optional correction) of some common mistakes
- user defined default base INCAR parameter specifications
- tags and values are not case sensitive 

## Options

The following outlines options for input options that do not follow the traditional 'tag = value' convention in VASP. 
___


### MAGMOM

The `magmom` tag is now broken into several options. You may specify the magnetic moment as a single number or a comma separated array for non-collinear moments. Additionally, you may specify magnetic moments from within the POSCAR if you so wish. 

Option | **Format** | Datatypes 
---    |    ---     | ---       
species |  `symbol:moment` \| `symbol:moments`  | `str:number` \| `str:list` 
sites   |  `site:moment`   \| `site:moments`    | `str:number` \| `str:list` 
index   |  `index:moment` \| `index:moments`    | `str:number` \| `str:list` 
string  |  `expression`    |  `str`     
poscar  |  `status`        |  `bool`  
all     |  `moment`        |  `number`


### LDAUU/LDAUJ

Option  | **Format**            | Datatypes 
---     |    ---                | ---       
species | `symbol:correction`   | `str:number` 
sites   |  `site:correction`    | `str:number`
index   |   `index:correction`  | `integer:number`
string  |  `expression`         | `str`       


### validation

Option  | **Format** | Datatypes | Notes | Default
---     |    ---     | ---       | ---   | --- 
warn    |  `status`  | `boolean` | Notify the user if possible mistakes are found | `false`
correct | `status`   | `boolean` | Automatically correct errors | `false` 


___ 


 
