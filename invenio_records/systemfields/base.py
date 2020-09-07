# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2020 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""The core of the system fields implementation."""

import inspect

from ..extensions import ExtensionMixin, RecordExtension, RecordMeta


def _get_fields(attrs, field_class):
    """Get system fields from a class' attributes dict.

    :param attrs: Dict of class' attributes.
    :param field_class: Base class for all system fields.
    """
    fields = {}
    for name, val in attrs.items():
        if isinstance(val, field_class):
            fields[name] = val
    return fields


def _get_inherited_fields(class_, field_class):
    """Get system fields from all base classes respecting the MRO.

    :param class_: The class that has just been constructed.
    :param field_class: Base class for all system fields.
    """
    # The variable mro holds a list of all super classes of "class_", in
    # correct MRO (mehtod resolution order). This ensures that we respect
    # Python inheritance rules when the same field is defined in both
    # the class and one or more super classes.
    mro = inspect.getmro(class_)

    fields = {}

    # Reverse order through MRO so that a field is taken from the most
    # specific class.
    for base in reversed(mro):
        fields.update(_get_fields(base.__dict__, field_class))
    return fields


class SystemField(ExtensionMixin):
    """Base class for all system fields.

    A system field is a Python data descriptor set on a record class that can
    also hook into a record via the extensions API (e.g on record creation,
    dumping etc).


    See :py:class:`~invenio_records.extensions.ExtensionMixin` for the full
    interface of methods that a field can override to hook into the record
    API.
    """

    #
    # Data descriptor definition
    #
    def __get__(self, instance, class_):
        r"""Accessing the object attribute.

        A subclass that overwrites this method, should handle two cases:

        1. Class access - If ``instance`` is None, the field is accessed
           through the class (e.g. Record.myfield). In this case the field
           itself should be returned.
        2. Instance access -  If ``instance`` is not None, the field is
           accessed through an instance of the class (e.g. record``.myfield``).

        A simple example is provided below:

        .. code-block:: python

            def __get__(self, instance, class_):
                if instance is None:
                    return self  # returns the field itself.
                if 'mykey' in instance:
                    return instance['mykey']
                return None

        :param instance: The instance through which the field is being accessed
                         or ``None`` if the field is accessed through the
                         class.
        :param class_: The ``class_`` which owns the field. In most cases you
                       should use this variable.
        """
        # Class access
        # - by default a system field accessed through a class (e.g.
        #   Record.myattr will return the field itself).
        if instance is None:
            return self
        # Instance access
        # - by default a system field accessed through an object instance (e.g.
        #   record.myattr will raise an Attribute error)
        raise AttributeError

    def __set__(self, instance, value):
        """Setting the attribute (instance access only).

        This method only handles set operations from an instance (e.g.
        ``record.myfield = val``). This is opposite to ``__get__()`` which
        needs to handle both class and instance access.
        """
        raise AttributeError()


class SystemFieldsExt(RecordExtension):
    """Record extension for system fields.

    This extension is responsible for iterating over all declared system fields
    on a class for each extension point.
    """

    def __init__(self, declared_fields):
        """Save the declared fields on the extension."""
        self.declared_fields = declared_fields

    def _run(self, method, *args, **kwargs):
        for field in self.declared_fields.values():
            getattr(field, method)(*args, **kwargs)

    def pre_init(self, *args, **kwargs):
        """Called when a new record instance is initialized."""
        self._run('pre_init', *args, **kwargs)

    def pre_dump(self, *args, **kwargs):
        """Called before a record is dumped."""
        self._run('pre_dump', *args, **kwargs)

    def post_load(self, *args, **kwargs):
        """Called after a record is loaded."""
        self._run('post_load', *args, **kwargs)

    def post_create(self, *args, **kwargs):
        """Called after a record is created."""
        self._run('post_create', *args, **kwargs)

    def pre_commit(self, *args, **kwargs):
        """Called before a record is committed."""
        self._run('pre_commit', *args, **kwargs)

    def pre_delete(self, *args, **kwargs):
        """Called before a record is deleted."""
        self._run('pre_delete', *args, **kwargs)

    def post_delete(self, *args, **kwargs):
        """Called after a record is deleted."""
        self._run('post_delete', *args, **kwargs)

    def pre_revert(self, *args, **kwargs):
        """Called before a record is reverted."""
        self._run('pre_revert', *args, **kwargs)

    def post_revert(self, *args, **kwargs):
        """Called after a record is reverted."""
        self._run('post_revert', *args, **kwargs)


class SystemFieldsMeta(RecordMeta):
    """Metaclass for a record class that integrates system fields."""

    def __new__(mcs, name, bases, attrs):
        """Create a new record class."""
        # Construct the class (and initialise the extension registry).
        class_ = super().__new__(mcs, name, bases, attrs)

        # Get system fields and ensure inheritance is respected.
        declared_fields = _get_inherited_fields(class_, SystemField)
        declared_fields.update(_get_fields(attrs, SystemField))

        # Register the system fields extension on the record class.
        class_._extensions.append(SystemFieldsExt(declared_fields))

        return class_


class SystemFieldsMixin(metaclass=SystemFieldsMeta):
    """Mixin class for records that add system fields capabilities.

    This class is primarily syntax sugar for being able to do::

      class MyRecord(Record, SystemsFieldsMixin):
          pass

    instead of::

      class MyRecord(Record, metaclass=SystemFieldsMeta):
          pass

    There are subtle differences though between the two above methods. Mainly
    which classes will execute the ``__new__()`` method on the metaclass.
    """