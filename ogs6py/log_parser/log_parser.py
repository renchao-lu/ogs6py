#!/usr/bin/env python

# Copyright (c) 2012-2021, OpenGeoSys Community (http://www.opengeosys.org)
#            Distributed under a Modified BSD License.
#              See accompanying file LICENSE.txt or
#              http://www.opengeosys.org/project/license

# pylint: disable=C0103, R0902, R0914, R0913
import re
import sys
from dataclasses import dataclass, field
import pandas as pd
from typing import List

@dataclass
class ComponentConvergence(object):
    number: int
    dx: float
    x: float
    dx_relative: float
    index_name: str = "component_convergence/"

    def to_dict(self, prefix):
        yield {
            prefix + self.index_name + "number": self.number,
            prefix + self.index_name + "dx": self.dx,
            prefix + self.index_name + "x": self.x,
            prefix + self.index_name + "dx_relative": self.dx_relative,
        }


@dataclass
class Iteration(object):
    number: int
    assembly_time: float  # seconds
    dirichlet_bc_time: float  # seconds
    linear_solver_time: float  # seconds
    cpu_time: float  # seconds
    phase_field_parameter: float
    component_convergence: List[ComponentConvergence] = field(default_factory=list)
    index_name: str = "iteration/"

    def _dict(self, prefix):
        return {
            prefix + self.index_name + "number": self.number,
            prefix + self.index_name + "assembly_time": self.assembly_time,
            prefix + self.index_name + "dirichlet_bc_time": self.dirichlet_bc_time,
            prefix + self.index_name + "linear_solver_time": self.linear_solver_time,
            prefix + self.index_name + "cpu_time": self.cpu_time,
            prefix + self.index_name + "phase_field_parameter": self.phase_field_parameter,
        }

    def to_dict(self, prefix):
        for c in self.component_convergence:
            for d in c.to_dict(prefix + self.index_name):
                yield self._dict(prefix) | d


@dataclass
class TimeStep(object):
    number: int
    t: float  # simulation time
    dt: float  # simulation time increment
    iterations: List[Iteration] = field(default_factory=list)
    cpu_time: float = None  # seconds
    output_time: float = None  # seconds
    index_name: str = "time_step/"

    def _dict(self):
        return {
            self.index_name + "number": self.number,
            self.index_name + "t": self.t,
            self.index_name + "dt": self.dt,
            self.index_name + "cpu_time": self.cpu_time,
            self.index_name + "output_time": self.output_time,
        }

    def to_dict(self, prefix):
        for i in self.iterations:
            for d in i.to_dict(self.index_name):
                yield self._dict() | d


@dataclass
class Simulation(object):
    timesteps: List[TimeStep] = field(default_factory=list)
    mesh_read_time: float = None  # seconds
    execution_time: float = None  # seconds

    def __len__(self):
        """Number of time steps"""
        return len(self.timesteps)

    def _dict(self):
        return {
            "execution_time": self.execution_time,
        }

    def __iter__(self):
        for t in self.timesteps:
            for d in t.to_dict(""):
                yield self._dict() | d


_re_iteration = [
    re.compile("info: \[time\] Iteration #(\d+) took ([\d\.e+s]+) s"),
    int,
    float,
]
_re_time_step_start = [
    re.compile(
        "info: === Time stepping at step #(\d+) and time ([\d\.e+s]+) with step size (.*)"
    ),
    int,
    float,
    float,
]
_re_time_step_output = [
    re.compile("info: \[time\] Output of timestep (\d+) took ([\d\.e+s]+) s"),
    int,
    float,
]
_re_time_step_solution_time = [
    re.compile(
        "info: \[time\] Solving process #(\d+) took ([\d\.e+s]+) s in time step #(\d+)"
    ),
    int,
    float,
    int,
]
_re_time_step_finished = [
    re.compile("info: \[time\] Time step #(\d+) took ([\d\.e+s]+) s"),
    int,
    float,
]

_re_assembly_time = [re.compile("info: \[time\] Assembly took ([\d\.e+s]+) s"), float]
_re_dirichlet_bc_time = [
    re.compile("info: \[time\] Applying Dirichlet BCs took ([\d\.e+s]+) s"),
    float,
]
_re_linear_solver_time = [
    re.compile("info: \[time\] Linear solver took ([\d\.e+s]+) s"),
    float,
]
_re_phase_field_parameter = [
    re.compile("info: The min of d is ([\d\.e+s]+)"),
    float,
]
# _re_reading_mesh = [re.compile(".*?time.*?Reading the mesh took ([\d\.e+s]+) s"), float]
_re_execution_time = [re.compile("info: \[time\] Execution took ([\d\.e+s]+) s"), float]

_re_component_convergence = [
    re.compile(
        "info: Convergence criterion, component (\d+): \|dx\|=([\d\.e+-]+), \|x\|=([\d\.e+-]+), \|dx\|/\|x\|=([\d\.e+-]+)$"
    ),
    int,
    float,
    float,
    float,
]

_re_convergence = [
    re.compile(
        "info: Convergence criterion: \|dx\|=([\d\.e+-]+), \|x\|=([\d\.e+-]+), \|dx\|/\|x\|=([\d\.e+-]+)$"
    ),
    float,
    float,
    float,
]

def _tryMatch(line: str, regex: re.Pattern, *ctors):
    if match := regex.match(line):
        return [ctor(s) for ctor, s in zip(ctors, match.groups())]
    return None


def parse_file(filename, maximum_timesteps=None, maximum_lines=None, petsc=False):

    tss = []
    execution_time = None
    mesh_read_time = None

    ts = TimeStep(
        number=0,
        t=0.0,  # Note: initial time is not set correctly.
        dt=None,
        iterations=[],
        cpu_time=None,
    )

    assembly_time = None
    dirichlet_bc_time = None
    linear_solver_time = None
    phase_field_parameter = None
    component_convergence = []

    number_of_lines_read = 0
    for line in open(filename):
        if petsc is True:
            line_new = line.replace('[0] ', '')
        else:
            line_new = line
        number_of_lines_read += 1

        if r := _tryMatch(line_new, *_re_iteration):
            ts.iterations.append(
                Iteration(
                    number=r[0],
                    assembly_time=assembly_time,
                    dirichlet_bc_time=dirichlet_bc_time,
                    linear_solver_time=linear_solver_time,
                    component_convergence=component_convergence,
                    cpu_time=r[1],
                    phase_field_parameter=phase_field_parameter
                )
            )
            # Reset parsed quantities to avoid reusing old values for next iterations
            assembly_time = None
            dirichlet_bc_time = None
            linear_solver_time = None
            phase_field_parameter = None
            component_convergence = []
            continue

        if r := _tryMatch(line_new, *_re_assembly_time):
            assembly_time = r[0]
            continue

        if r := _tryMatch(line_new, *_re_dirichlet_bc_time):
            dirichlet_bc_time = r[0]
            continue

        if r := _tryMatch(line_new, *_re_linear_solver_time):
            linear_solver_time = r[0]
            continue

        if r := _tryMatch(line_new, *_re_phase_field_parameter):
            phase_field_parameter = r[0]
            continue

        if r := _tryMatch(line_new, *_re_component_convergence):
            component_convergence.append(
                ComponentConvergence(number=r[0], dx=r[1], x=r[2], dx_relative=r[3])
            )
            continue

        if r := _tryMatch(line_new, *_re_convergence):
            component_convergence.append(
                ComponentConvergence(number=0, dx=r[0], x=r[1], dx_relative=r[2])
            )
            continue

        if r := _tryMatch(line_new, *_re_time_step_start):
            # print("Finished ts", ts)
            tss.append(ts)
            ts = TimeStep(number=r[0], t=r[1], dt=r[2])
            # print("New timestep", ts, "\n")
            if (
                ts
                and (maximum_timesteps is not None)
                and (ts.number > maximum_timesteps)
            ) or ((maximum_lines is not None) and (number_of_lines_read >
                    maximum_lines)):
                break
            continue

        if r := _tryMatch(line_new, *_re_time_step_solution_time):
            ts.solution_time = r[1]
            continue

        if r := _tryMatch(line_new, *_re_time_step_output):
            ts.output_time = r[1]
            continue

        if r := _tryMatch(line_new, *_re_time_step_finished):
            ts.cpu_time = r[1]
            continue

        # if r := _tryMatch(line, *_re_reading_mesh):
        #    mesh_read_time = r[0]
        #    continue

        if r := _tryMatch(line_new, *_re_execution_time):
            execution_time = r[0]

            # print("Finished ts", ts)
            tss.append(ts)
            continue
    return Simulation(
        timesteps=tss, mesh_read_time=mesh_read_time, execution_time=execution_time
    )
if __name__ == "__main__":
    filename = sys.argv[1]
    data = parse_file(sys.argv[1], maximum_timesteps=None, maximum_lines=None, petsc=True)
    print(data)
    df = pd.DataFrame(data)
    print(df)
    filename_prefix = filename.split('.')[0]
    df.to_csv(f"{filename_prefix}.csv")
