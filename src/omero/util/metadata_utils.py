#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2015 University of Dundee & Open Microscopy Environment.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Utilities for manipulating bulk-annotations

Includes classes to help with basic data-munging (TODO), and for formatting
data for clients.
"""

import re


class BulkAnnotationConfiguration(object):
    """
    Parent class for handling bulk-annotation column configurations
    """

    def __init__(self, default_cfg, column_cfgs):
        """
        :param default_cfg: Dict of default values, can be empty
        :params column_cfgs: Array of dicts of column configurations
        """
        self.defaults = self.get_default_cfg(default_cfg)
        self.column_cfgs = [self.get_column_config(c) for c in column_cfgs]

    @staticmethod
    def get_default_cfg(cfg):
        """
        Get the default column configuration, fill in unspecified fields
        """
        default_defaults = {
            "clientvalue": "{{ value }}",
            "includeclient": True,
            "include": True,
            "split": False,
            "type": "string",
            "visible": True,
        }
        if not cfg:
            cfg = {}

        invalid = set(cfg.keys()).difference(default_defaults.keys())
        if invalid:
            raise Exception(
                "Invalid key(s) in column defaults: %s" % list(invalid))

        defaults = default_defaults.copy()
        defaults.update(cfg)
        return defaults

    @staticmethod
    def validate_column_config(cfg):
        """
        Check whether a column config section is valid, throws Exception if not
        """
        required = {"name"}
        optional = {
            "clientname",
            "clientvalue",
            "includeclient",
            "position",
            "include",
            "split",
            "type",
            "visible"
            }

        keys = set(cfg.keys())

        missing = required.difference(keys)
        if missing:
            raise Exception(
                "Required key(s) missing from column configuration: %s" %
                list(missing))

        if not cfg["name"]:
            raise Exception("Empty name in column configuration: %s" % cfg)

        invalid = keys.difference(optional.union(required))
        if invalid:
            raise Exception(
                "Invalid key(s) in column configuration: %s" % list(invalid))

        try:
            subbed = re.sub("\{\{\s*value\s*\}\}", '', cfg["clientvalue"])
            m = re.search("\{\{[\s\w]*}\}", subbed)
            if m:
                raise Exception(
                    "clientvalue template parameter not found: %s" % m.group())
        except KeyError:
            pass

    def get_column_config(self, cfg):
        """
        Replace unspecified fields in a column config with defaults
        """
        self.validate_column_config(cfg)
        column_cfg = self.defaults.copy()
        column_cfg.update(cfg)
        return column_cfg


class KeyValueListPassThrough(object):
    """
    Converts bulk-annotation rows into key-value lists without any
    transformation
    """

    def __init__(self, headers, default_cfg=None, column_cfgs=None):
        """
        :param headers: A list of table headers
        """
        self.headers = headers

    def transform_gen(self, values):
        """
        Generator which transforms table rows
        :param values: An iterable of table rows
        :return: A generator which returns rows in the form
                 [(k1, v1), (k2 v2), ...]
        """
        for rowvals in values:
            assert len(rowvals) == len(self.headers)
            yield zip(self.headers, rowvals)


class KeyValueListTransformer(BulkAnnotationConfiguration):
    """
    Converts bulk-annotation rows into key-value lists
    """

    def __init__(self, headers, default_cfg, column_cfgs):
        """
        :param headers: A list of table headers
        """
        # TODO: decide what to do with unmentioned columns
        super(KeyValueListTransformer, self).__init__(
            default_cfg, column_cfgs)
        self.headerindexmap = dict((b, a) for (a, b) in enumerate(headers))
        self.output_configs = []
        for n in xrange(len(self.column_cfgs)):
            cfg = self.column_cfgs[n]
            self.output_configs.append((cfg, self.headerindexmap[cfg["name"]]))

    def transform1(self, value, cfg):
        """
        Process a single value corresponding to a single table row-column

        :return: The key and a list of [value]. In general [values] will be
                 a single item unless `split` is specified in cfg in which
                 case there may be multiple.
        """

        def valuesub(v, cv):
            return re.sub("\{\{\s*value\s*\}\}", v, cv)

        key = cfg["name"]
        try:
            key = cfg["clientname"]
        except KeyError:
            pass

        try:
            if not cfg["visible"]:
                key = "__%s" % key
        except KeyError:
            pass

        if "split" in cfg and cfg["split"]:
            values = [v.strip() for v in value.split(cfg["split"])]
        else:
            values = [value]

        if "clientvalue" in cfg:
            values = [valuesub(v, cfg["clientvalue"]) for v in values]
        return key, values

    def transform(self, rowvalues):
        """
        Transform a table rows
        :param rowvalues: A table row
        :return: The transformed rows in the form [(k1, v1), (k2 v2), ...].
                 v* will be a list, in most cases of length one unless the
                 `split` configuration option is enabled for this column.
        """
        assert len(rowvalues) == len(self.headerindexmap)
        rowkvs = [self.transform1(rowvalues[i], c)
                  for (c, i) in self.output_configs]
        return rowkvs


def print_kvs(headers, values, default_cfg, column_cfgs):
    tr = KeyValueListTransformer(headers, default_cfg, column_cfgs)
    n = -1
    for row in values:
        n += 1
        transformed = tr.transform(row)
        for k, vs in transformed:
            if not isinstance(vs, list):
                vs = [vs]
            for v in vs:
                print "% 2d % 10s : %s" % (n, k, v)
