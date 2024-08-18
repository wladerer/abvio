# Automatic Generation of PBS/Slurm scripts

There is an experimental feature that allows you to create PBS/SLURM scripts. It is able to take the same input arguments and produce either a PBS or Slurm script with the appropriate directives. In the future, this will be integrated into the entire checking system to ensure the user has provided the correct executable (gamma, noncollinear, standard) and potential options for automatic parallelization optimality between incar, structure, and system hardware. 

Using this functionality is quite simple, an example of a complete input file is the following

```yaml 
incar:
  ediff: 1e-6
  ediffg: -0.01
  encut: 600
  nsw: 25
  ibrion: 2
  isif: 3
  nelm: 99 
  magmom: 
      Ca: 0.0
      Ti: 2.0
      O: 0.0
  lwave: false
structure:
  mode: prototype
  prototype: perovskite
  species: [Ca, Ti, O]
  lattice:
    a: 3.889471
kpoints:
  mode: gamma
  spacing: [7, 7, 7]
job:
  scheduler: 'slurm'
  directives_dict:
    nodes: 2
    cores: 4
    memory: '8G'
    shebang: '#!/bin/bash'
    script:
      - 'echo "Hello World"'
      - 'echo "Goodbye World"'
```

Which will create a VASP input set that contains the following files 

### INCAR

```
EDIFF = 1e-6
EDIFFG = -0.01
ENCUT = 600
IBRION = 2
ISIF = 3
LWAVE = False
MAGMOM = 1*0.0 1*2.0 3*0.0
NELM = 99
NSW = 25
```

### POSCAR

```
Ca1 Ti1 O3
1.0
   3.8894709999999999    0.0000000000000000    0.0000000000000000
   0.0000000000000000    3.8894709999999999    0.0000000000000000
   0.0000000000000000    0.0000000000000000    3.8894709999999999
Ca Ti O
1 1 3
direct
   0.0000000000000000    0.0000000000000000    0.0000000000000000 Ca
   0.5000000000000000    0.5000000000000000    0.5000000000000000 Ti
   0.5000000000000000    0.0000000000000000    0.5000000000000000 O
   0.0000000000000000    0.5000000000000000    0.5000000000000000 O
   0.5000000000000000    0.5000000000000000    0.0000000000000000 O

```

### KPOINTS

```
Automatic kpoint scheme
0
Gamma
7 7 7
```

### submit.sh

```bash
#!/bin/bash
#SBATCH -J vaspslurm
#SBATCH -n 1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH -t 00:30:00
#SBATCH --nodes=2
echo "Hello World"
echo "Goodbye World

```

We can change the `scheduler` value to 'pbs' and would produce the following

```bash
#!/bin/bash
#PBS -N vasppbs
#PBS -l select=1:ncpus=4:mem=7630MB
#PBS -l walltime=00:30:00
#PBS -l nodes=2
echo "Hello World"
echo "Goodbye World"
```

I hope this provides you with some portability in generating equivalent jobs across different HPCs. 