#!/usr/bin/env python3
#
# Copyright (C) 2022 Brigham Young University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

'''
    conftest.py
    BYU Configurable Computing Lab (CCL): BFAT project, 2022

    Simple pytest configuration script for running unit tests on BFAT
'''

import pytest

def pytest_addoption(parser):
    parser.addoption('--dcp', action='store',
                     help='Path to design checkpoint file used for unit testing')
    parser.addoption('--keep_files', action='store_true', default=False,
                     help='Flag to not delete testing files when tests finish')

@pytest.fixture
def dcp(request):
    return request.config.getoption('--dcp')

@pytest.fixture
def keep_files(request):
    return request.config.getoption('--keep_files')
