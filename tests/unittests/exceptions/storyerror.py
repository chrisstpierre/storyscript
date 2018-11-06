# -*- coding: utf-8 -*-
import os

from pytest import fixture, mark

from storyscript.exceptions import StoryError


@fixture
def error(magic):
    return magic()


@fixture
def storyerror(error):
    return StoryError(error, 'story')


def test_storyerror_init(storyerror, error):
    assert storyerror.error == error
    assert storyerror.story == 'story'
    assert storyerror.path is None
    assert issubclass(StoryError, SyntaxError)


def test_storyerror_init_path():
    storyerror = StoryError('error', 'story', path='hello.story')
    assert storyerror.path == 'hello.story'


def test_storyerror_name(storyerror):
    assert storyerror.name() == 'story'


def test_storyerror_name_path(patch, storyerror):
    patch.object(os, 'getcwd', return_value='/abspath')
    storyerror.path = 'hello.story'
    assert storyerror.name() == 'hello.story'


def test_storyerror_name_reduce_path(patch, storyerror):
    """
    Ensures that paths are simplified for stories in the current working
    directory.
    """
    patch.object(os, 'getcwd', return_value='/abspath')
    storyerror.path = '/abspath/hello.story'
    assert storyerror.name() == 'hello.story'


def test_storyerror_get_line(patch, storyerror, error):
    """
    Ensures get_line returns the error line
    """
    error.line = '1'
    storyerror.story = 'x = 0\ny = 1'
    assert storyerror.get_line() == 'x = 0'


def test_storyerror_header(patch, storyerror, error):
    """
    Ensures header returns the correct text.
    """
    patch.object(StoryError, 'name')
    template = 'Error: syntax error in {} at line {}, column {}'
    args = (StoryError.name(), error.line, error.column)
    assert storyerror.header() == template.format(*args)


def test_storyerror_symbols(patch, storyerror, error):
    del error.end_column
    error.column = '1'
    assert storyerror.symbols() == '^'


def test_story_error_symbols_end_column(patch, storyerror, error):
    error.end_column = '4'
    error.column = '1'
    assert storyerror.symbols() == '^^^'


def test_storyerror_highlight(patch, storyerror, error):
    """
    Ensures StoryError.highlight produces the correct text.
    """
    patch.many(StoryError, ['get_line', 'symbols'])
    error.column = '1'
    result = storyerror.highlight()
    highlight = '{}{}'.format(' ' * 6, StoryError.symbols())
    args = (error.line, StoryError.get_line(), highlight)
    assert result == '{}|    {}\n{}'.format(*args)


def test_storyerror_hint(storyerror, error):
    del error.error
    assert storyerror.hint() == ''


@mark.parametrize('name, message', [
    ('service-name', "A service name can't contain `.`"),
    ('arguments-noservice', 'You have defined an argument, but not a service'),
    ('return-outside', '`return` is allowed only inside functions'),
    ('variables-backslash', "A variable name can't contain `/`"),
    ('variables-dash', "A variable name can't contain `-`")
])
def test_storyerror_hint_error(storyerror, error, name, message):
    error.error = name
    assert storyerror.hint() == message


def test_storyerror_message(patch, storyerror):
    patch.many(StoryError, ['header', 'highlight', 'hint'])
    args = (storyerror.header(), storyerror.highlight(), storyerror.hint())
    assert storyerror.message() == '{}\n\n{}\n\n{}'.format(*args)


def test_storyerror_echo(capsys, patch, storyerror):
    """
    Ensures StoryError.echo prints StoryError.message
    """
    patch.object(StoryError, 'message')
    storyerror.echo()
    output, error = capsys.readouterr()
    assert output == '{}\n'.format(StoryError.message())