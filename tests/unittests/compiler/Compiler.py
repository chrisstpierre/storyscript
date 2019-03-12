# -*- coding: utf-8 -*-
from lark.lexer import Token

from pytest import fixture, mark, raises

from storyscript.Version import version
from storyscript.compiler import Compiler, Lines, Objects, Preprocessor
from storyscript.exceptions import CompilerError, StorySyntaxError
from storyscript.parser import Tree


@fixture
def lines(magic):
    return magic()


@fixture
def compiler(patch, lines):
    patch.init(Lines)
    compiler = Compiler()
    compiler.lines = lines
    return compiler


def test_compiler_init(patch):
    patch.init(Lines)
    compiler = Compiler()
    assert isinstance(compiler.lines, Lines)


def test_compiler_output(tree):
    tree.children = [Token('token', 'output')]
    result = Compiler.output(tree)
    assert result == ['output']


def test_compiler_output_none():
    assert Compiler.output(None) == []


def test_compiler_extract_values(patch, tree):
    patch.object(Objects, 'entity')
    tree.expression = None
    result = Compiler.extract_values(tree)
    tree.child.assert_called_with(1)
    Objects.entity.assert_called_with(tree.child())
    assert result == [Objects.entity()]


def test_compiler_extract_values_expression(patch, tree):
    patch.object(Objects, 'expression')
    tree.expression.mutation = None
    result = Compiler.extract_values(tree)
    Objects.expression.assert_called_with(tree.expression)
    assert result == [Objects.expression()]


def test_compiler_extract_values_mutation(patch, tree):
    patch.many(Objects, ['values', 'mutation_fragment'])
    result = Compiler.extract_values(tree)
    Objects.values.assert_called_with(tree.expression.values)
    Objects.mutation_fragment.assert_called_with(tree.expression.mutation)
    assert result == [Objects.values(), Objects.mutation_fragment()]


def test_compiler_chained_mutations(patch, magic, tree):
    patch.object(Objects, 'mutation_fragment')
    mutation = magic()
    tree.find_data.return_value = [mutation]
    result = Compiler.chained_mutations(tree)
    Objects.mutation_fragment.assert_called_with(mutation.mutation_fragment)
    assert result == [Objects.mutation_fragment()]


def test_compiler_function_output(patch, tree):
    patch.object(Compiler, 'output')
    result = Compiler.function_output(tree)
    tree.node.assert_called_with('function_output.types')
    assert result == Compiler.output()


def test_compiler_imports(patch, compiler, lines, tree):
    compiler.lines.modules = {}
    compiler.imports(tree, '1')
    module = tree.child(1).value
    assert lines.modules[module] == tree.string.child(0).value[1:-1]


def test_compiler_absolute_expression(patch, compiler, lines, tree):
    patch.object(Objects, 'expression')
    compiler.absolute_expression(tree, '1')
    Objects.expression.assert_called_with(tree.expression)


def test_compiler_assignment_unary(patch, compiler, lines, tree):
    """
    Ensures a line like "x = value" is compiled correctly
    """
    patch.many(Objects, ['names', 'entity', 'expression'])
    af = tree.assignment_fragment.base_expression
    af.expression.is_unary_leaf.return_value = True
    af.service = None
    af.mutation = None
    lines.lines = {lines.last(): {'method': None}}
    compiler.assignment(tree, '1')
    Objects.names.assert_called_with(tree.path)
    Objects.expression.assert_called_with(af.expression)
    kwargs = {'args': [Objects.expression()],
              'parent': '1'}
    lines.append.assert_called_with('expression', tree.line(), **kwargs)
    lines.set_name.assert_called_with(Objects.names())
    assert lines.lines[compiler.lines.last()]['method'] == 'set'


def test_compiler_assignment_service(patch, compiler, lines, tree):
    patch.object(Objects, 'names')
    patch.object(Compiler, 'service')
    lines.is_variable_defined.return_value = False
    compiler.assignment(tree, '1')
    service = tree.assignment_fragment.base_expression.service
    Compiler.service.assert_called_with(service, None, '1')
    lines.set_name.assert_called_with(Objects.names())


def test_compiler_assignment_mutation(patch, compiler, lines, tree):
    """
    Ensures that assignments to mutations are compiled correctly.
    """
    patch.object(Objects, 'names', return_value='name')
    patch.object(Compiler, 'mutation_block')
    af = tree.assignment_fragment.base_expression
    af.service = None
    compiler.assignment(tree, '1')
    Compiler.mutation_block.assert_called_with(af, '1')
    lines.set_name.assert_called_with('name')


def test_compiler_assignment_expression(patch, compiler, lines, tree):
    patch.object(Objects, 'names', return_value='name')
    patch.object(Objects, 'expression')
    af = tree.assignment_fragment.base_expression
    af.service = None
    af.mutation = None
    af.expression.is_unary_leaf.return_value = False
    compiler.assignment(tree, '1')
    Objects.expression.assert_called_with(af.expression)
    lines.set_name.assert_called_with('name')


def test_compiler_assignment_function_call(patch, compiler, lines, tree):
    """
    Ensures that assignments with function calls are compiled correctly.
    """
    patch.object(Objects, 'names', return_value='name')
    patch.object(Compiler, 'call_expression')
    af = tree.assignment_fragment.base_expression
    af.service = None
    af.mutation = None
    af.expression = None
    compiler.assignment(tree, '1')
    Compiler.call_expression.assert_called_with(af.call_expression, '1')
    lines.set_name.assert_called_with('name')


def test_compiler_arguments(patch, compiler, lines, tree):
    patch.object(Objects, 'arguments')
    lines.last.return_value = '1'
    lines.lines = {'1': {'method': 'execute', 'args': ['args']}}
    compiler.arguments(tree, '0')
    Objects.arguments.assert_called_with(tree)
    assert lines.lines['1']['args'] == ['args'] + Objects.arguments()


def test_compiler_arguments_fist_line(patch, compiler, lines, tree):
    """
    Ensures that if this is the first line, an error is raised.
    """
    patch.init(StorySyntaxError)
    lines.last.return_value = None
    with raises(StorySyntaxError):
        compiler.arguments(tree, '0')
    error = 'arguments_noservice'
    StorySyntaxError.__init__.assert_called_with(error, tree=tree)


def test_compiler_arguments_not_execute(patch, compiler, lines, tree):
    """
    Ensures that if the previous line is not an execute, an error is raised.
    """
    patch.init(StorySyntaxError)
    patch.object(Objects, 'arguments')
    lines.last.return_value = '1'
    lines.lines = {'1': {'method': 'whatever'}}
    with raises(StorySyntaxError):
        compiler.arguments(tree, '0')
    error = 'arguments_noservice'
    StorySyntaxError.__init__.assert_called_with(error, tree=tree)


def test_compiler_call_expression(patch, compiler, lines, tree):
    """
    Ensures that function call expression can be compiled
    """
    patch.many(Objects, ['arguments', 'names'])
    Objects.names.return_values = ['.path.']
    compiler.call_expression(tree, 'parent')
    Objects.arguments.assert_called_with(tree)
    lines.append.assert_called_with('call', tree.line(),
                                    service=tree.path.extract_path(),
                                    args=Objects.arguments(), parent='parent',
                                    output=None)


def test_compiler_call_expression_no_inline(patch, compiler, tree):
    """
    Ensures that function call expression checks its arguments correctly
    """
    patch.object(Objects, 'arguments')
    tree.expect.side_effect = Exception('.')
    tree.path.inline_expression = True
    with raises(Exception):
        compiler.call_expression(tree, 'parent')
    tree.expect.assert_called_with(False, 'function_call_no_inline_expression')


def test_compiler_call_expression_no_invalid_path(patch, compiler, tree):
    """
    Ensures that function call expression checks its arguments correctly
    """
    patch.many(Objects, ['arguments', 'names'])
    error_code = None
    args = None

    def expect(cond, _error_code, **_args):
        nonlocal error_code, args
        if not cond:
            assert args is None
            args = _args
            error_code = _error_code

    tree.expect = expect
    tree.path.inline_expression = None
    Objects.names.return_value = ['a', 'b']
    name = tree.path.extract_path()
    compiler.lines.functions = [name]

    compiler.call_expression(tree, 'parent')
    assert error_code == 'function_call_invalid_path'
    assert args == {'name': 'a.b'}


def test_compiler_call_expression_no_function(patch, compiler, tree):
    """
    Ensures that function call expression checks its arguments correctly
    """
    patch.many(Objects, ['arguments', 'names'])

    error_code = None
    args = None

    def expect(cond, _error_code, **_args):
        nonlocal error_code, args
        if not cond:
            assert args is None
            args = _args
            error_code = _error_code

    tree.expect = expect
    Objects.names.return_value = ['path']
    tree.path.inline_expression = None
    name = tree.path.extract_path()

    compiler.call_expression(tree, 'parent')
    assert error_code == 'function_call_no_function'
    assert args == {'name': name}


def test_compiler_call_expression_other_module(patch, compiler, tree):
    """
    Ensures that function call expression checks its arguments correctly
    when calling a function from another module
    """
    patch.many(Objects, ['arguments', 'names'])

    def expect(cond, _error_code, **_args):
        assert cond, _error_code

    Objects.names.return_value = ['path']
    tree.expect = expect
    tree.path.inline_expression = None
    tree.path.extract_path.return_value = 'my_module.my_function'
    compiler.lines.modules = ['my_module']

    compiler.call_expression(tree, 'parent')


def test_compiler_call_expression_other_module_error(patch, compiler, tree):
    """
    Ensures that function call expression checks its arguments correctly
    when calling a function from another module
    """
    patch.many(Objects, ['arguments', 'names'])
    error_code = None
    args = None

    def expect(cond, _error_code, **_args):
        nonlocal error_code, args
        if not cond:
            assert args is None
            args = _args
            error_code = _error_code

    Objects.names.return_value = ['path']
    tree.expect = expect
    tree.path.inline_expression = None
    tree.path.extract_path.return_value = 'my_module2.my_function'
    compiler.lines.modules = ['my_module']
    name = tree.path.extract_path()

    compiler.call_expression(tree, 'parent')
    assert error_code == 'function_call_no_function'
    assert args == {'name': name}


def test_compiler_service(patch, compiler, lines, tree):
    """
    Ensures that service trees can be compiled
    """
    patch.object(Objects, 'arguments')
    patch.object(Compiler, 'output')
    tree.node.return_value = None
    compiler.service(tree, None, 'parent')
    line = tree.line()
    service = tree.path.extract_path()
    command = tree.service_fragment.command.child()
    Objects.arguments.assert_called_with(tree.service_fragment)
    Compiler.output.assert_called_with(tree.service_fragment.output)
    lines.execute.assert_called_with(line, service, command,
                                     Objects.arguments(), Compiler.output(),
                                     None, 'parent')


def test_compiler_service_command(patch, compiler, lines, tree):
    patch.object(Objects, 'arguments')
    patch.object(Compiler, 'output')
    compiler.service(tree, None, 'parent')
    line = tree.line()
    service = tree.path.extract_path()
    command = tree.service_fragment.command.child()
    lines.set_scope.assert_called_with(line, 'parent', Compiler.output())
    lines.execute.assert_called_with(line, service, command,
                                     Objects.arguments(), Compiler.output(),
                                     None, 'parent')


def test_compiler_service_nested_block(patch, magic, compiler, lines, tree):
    patch.object(Objects, 'arguments')
    patch.object(Compiler, 'output')
    tree.node.return_value = None
    nested_block = magic()
    compiler.service(tree, nested_block, 'parent')
    line = tree.line()
    service = tree.path.extract_path()
    command = tree.service_fragment.command.child()
    lines.execute.assert_called_with(line, service, command,
                                     Objects.arguments(), Compiler.output(),
                                     nested_block.line(), 'parent')


def test_compiler_service_no_output(patch, compiler, lines, tree):
    patch.object(Objects, 'arguments')
    patch.object(Compiler, 'output')
    Compiler.output.return_value = None
    compiler.service(tree, None, 'parent')
    assert lines.set_output.call_count == 0


def test_compiler_service_expressions(patch, compiler, lines, tree):
    """
    Ensures service trees that are infact mutations on paths are compiled
    correctly
    """
    patch.object(Objects, 'names', return_value='x')
    patch.object(Compiler, 'mutation_block')
    lines.variables = ['x']
    compiler.service(tree, None, 'parent')
    Objects.names.assert_called_with(tree.path)
    Compiler.mutation_block.assert_called_with(tree, 'parent')


def test_compiler_service_syntax_error(patch, compiler, lines, tree):
    patch.object(Objects, 'arguments')
    patch.object(Compiler, 'output')
    patch.object(StorySyntaxError, 'tree_position')
    lines.execute.side_effect = StorySyntaxError('error')
    with raises(StorySyntaxError):
        compiler.service(tree, None, 'parent')
    StorySyntaxError.tree_position.assert_called_with(tree)


def test_compiler_when(patch, compiler, lines, tree):
    patch.object(Compiler, 'service')
    lines.lines = {'1': {}}
    lines.last.return_value = '1'
    compiler.when(tree, 'nested_block', '1')
    Compiler.service.assert_called_with(tree.service, 'nested_block', '1')
    assert lines.lines['1']['method'] == 'when'


def test_compiler_when_path(patch, compiler, lines, tree):
    patch.object(Objects, 'path')
    patch.object(Compiler, 'output')
    tree.service = None
    compiler.when(tree, 'nested_block', '1')
    Objects.path.assert_called_with(tree.path)
    Compiler.output.assert_called_with(tree.output)
    lines.append.assert_called_with('when', tree.line(), args=[Objects.path()],
                                    output=Compiler.output(), parent='1')


def test_compiler_return_statement(patch, compiler, lines, tree):
    """
    Ensures Compiler.return_statement can compile return statements.
    """
    tree.base_expression = None
    compiler.return_statement(tree, '1')
    line = tree.line()
    kwargs = {'args': None, 'parent': '1'}
    lines.append.assert_called_with('return', line, **kwargs)


def test_compiler_return_statement_entity(patch, compiler, lines, tree):
    """
    Ensures Compiler.return_statement can compile return statements that return
    entities.
    """
    patch.object(Compiler, 'fake_base_expression')
    compiler.return_statement(tree, '1')
    line = tree.line()
    Compiler.fake_base_expression.assert_called_with(tree.base_expression, '1')
    kwargs = {'args': [Compiler.fake_base_expression()], 'parent': '1'}
    lines.append.assert_called_with('return', line, **kwargs)


def test_compiler_return_statement_error(patch, compiler, tree):
    """
    Ensures Compiler.return_statement raises CompilerError when the return
    is outside a function.
    """
    patch.object(Compiler, 'fake_base_expression')
    compiler.return_statement(tree, None)
    tree.expect.assert_called_with(False, 'return_outside')


def test_compiler_if_block(patch, compiler, lines, tree):
    patch.many(Compiler, ['subtree', 'fake_base_expression'])
    tree.elseif_block = None
    tree.else_block = None
    tree.extract.return_value = []
    compiler.if_block(tree, '1')
    exp = tree.if_statement.base_expression
    Compiler.fake_base_expression.assert_called_with(exp, '1')
    nested_block = tree.nested_block
    args = [Compiler.fake_base_expression()]
    lines.set_scope.assert_called_with(tree.line(), '1')
    lines.finish_scope.assert_called_with(tree.line())
    lines.append.assert_called_with('if', tree.line(), args=args,
                                    enter=nested_block.line(), parent='1')
    compiler.subtree.assert_called_with(nested_block, parent=tree.line())


def test_compiler_if_block_with_elseif(patch, compiler, tree):
    patch.many(Compiler, ['subtree', 'subtrees', 'fake_base_expression'])
    tree.else_block = None
    tree.extract.return_value = ['one']
    compiler.if_block(tree, '1')
    tree.extract.assert_called_with('elseif_block')
    compiler.subtrees.assert_called_with('one', parent='1')


def test_compiler_if_block_with_else(patch, compiler, tree):
    patch.many(Compiler, ['subtree', 'subtrees', 'fake_base_expression'])
    tree.extract.return_value = []
    compiler.if_block(tree, '1')
    compiler.subtrees.assert_called_with(tree.else_block, parent='1')


def test_compiler_elseif_block(patch, compiler, lines, tree):
    patch.many(Compiler, ['subtree', 'fake_base_expression'])
    compiler.elseif_block(tree, '1')
    lines.set_exit.assert_called_with(tree.line())
    exp = tree.elseif_statement.base_expression
    Compiler.fake_base_expression.assert_called_with(exp, '1')
    args = [Compiler.fake_base_expression()]
    lines.set_scope.assert_called_with(tree.line(), '1')
    lines.finish_scope.assert_called_with(tree.line())
    lines.append.assert_called_with('elif', tree.line(), args=args,
                                    enter=tree.nested_block.line(),
                                    parent='1')
    compiler.subtree.assert_called_with(tree.nested_block, parent=tree.line())


def test_compiler_else_block(patch, compiler, lines, tree):
    patch.object(Compiler, 'subtree')
    compiler.else_block(tree, '1')
    lines.set_exit.assert_called_with(tree.line())
    lines.set_scope.assert_called_with(tree.line(), '1')
    lines.finish_scope.assert_called_with(tree.line())
    lines.append.assert_called_with('else', tree.line(), parent='1',
                                    enter=tree.nested_block.line())
    compiler.subtree.assert_called_with(tree.nested_block, parent=tree.line())


def test_compiler_foreach_block(patch, compiler, lines, tree):
    patch.init(Tree)
    patch.object(Objects, 'entity')
    patch.many(Compiler, ['subtree', 'output'])
    compiler.foreach_block(tree, '1')
    assert Objects.entity.call_count == 1
    compiler.output.assert_called_with(tree.foreach_statement.output)
    args = [Objects.entity()]
    lines.set_scope.assert_called_with(tree.line(), '1', Compiler.output())
    lines.finish_scope.assert_called_with(tree.line())
    lines.append.assert_called_with('for', tree.line(), args=args,
                                    enter=tree.nested_block.line(),
                                    output=Compiler.output(), parent='1')
    compiler.subtree.assert_called_with(tree.nested_block, parent=tree.line())


def test_compiler_while_block(patch, compiler, lines, tree):
    patch.init(Tree)
    patch.many(Compiler, ['subtree', 'fake_base_expression'])
    compiler.while_block(tree, '1')
    args = [compiler.fake_base_expression()]
    lines.set_scope.assert_called_with(tree.line(), '1')
    lines.finish_scope.assert_called_with(tree.line())
    lines.append.assert_called_with('while', tree.line(), args=args,
                                    enter=tree.nested_block.line(),
                                    parent='1')
    compiler.subtree.assert_called_with(tree.nested_block, parent=tree.line())


def test_compiler_function_block(patch, compiler, lines, tree):
    patch.object(Objects, 'function_arguments')
    patch.many(Compiler, ['subtree', 'function_output'])
    compiler.function_block(tree, '1')
    statement = tree.function_statement
    Objects.function_arguments.assert_called_with(statement)
    compiler.function_output.assert_called_with(statement)
    lines.append.assert_called_with('function', tree.line(),
                                    function=statement.child().value,
                                    args=Objects.function_arguments(),
                                    output=compiler.function_output(),
                                    enter=tree.nested_block.line(),
                                    parent='1')
    compiler.subtree.assert_called_with(tree.nested_block, parent=tree.line())


def test_compiler_function_block_redeclared(patch, compiler, lines, tree):
    patch.object(Objects, 'function_arguments')
    patch.many(Compiler, ['subtree', 'function_output'])
    compiler.lines.functions = {'.function.': '0'}
    statement = tree.function_statement
    statement.child(1).value = '.function.'
    with raises(CompilerError) as e:
        compiler.function_block(tree, '1')

    e.value.format.function_name = '.function.'
    e.value.format.line = '0'
    e.value.error = 'function_already_declared'


def test_compiler_throw_statement(patch, compiler, lines, tree):
    tree.children = [Token('RAISE', 'throw')]
    compiler.throw_statement(tree, '1')
    lines.append.assert_called_with('throw', tree.line(), args=[],
                                    parent='1')


def test_compiler_throw_name_statement(patch, compiler, lines, tree):
    patch.object(Objects, 'entity')
    tree.children = [Token('RAISE', 'throw'), Token('NAME', 'error')]
    compiler.throw_statement(tree, '1')
    args = [Objects.entity()]
    lines.append.assert_called_with('throw', tree.line(), args=args,
                                    parent='1')


def test_compiler_mutation_block(patch, compiler, lines, tree):
    patch.many(Objects, ['entity', 'mutation_fragment'])
    patch.object(Compiler, 'chained_mutations', return_value=['chained'])
    tree.path = None
    tree.nested_block = None
    compiler.mutation_block(tree, None)
    Objects.entity.assert_called_with(tree.mutation.entity)
    Objects.mutation_fragment.assert_called_with(
        tree.mutation.mutation_fragment)
    Compiler.chained_mutations.assert_called_with(tree.mutation)
    args = [Objects.entity(), Objects.mutation_fragment(), 'chained']
    kwargs = {'args': args, 'parent': None}
    lines.append.assert_called_with('mutation', tree.line(), **kwargs)


def test_compiler_mutation_block_nested(patch, compiler, lines, tree):
    patch.many(Objects, ['entity', 'mutation_fragment'])
    patch.object(Compiler, 'chained_mutations', return_value=['chained'])
    tree.path = None
    compiler.mutation_block(tree, None)
    Compiler.chained_mutations.assert_called_with(tree.nested_block)
    args = [Objects.entity(), Objects.mutation_fragment(), 'chained',
            'chained']
    kwargs = {'args': args, 'parent': None}
    lines.append.assert_called_with('mutation', tree.line(), **kwargs)


def test_compiler_mutation_block_from_service(patch, compiler, lines, tree):
    patch.many(Objects, ['path', 'mutation_fragment'])
    patch.object(Compiler, 'chained_mutations', return_value=['chained'])
    tree.nested_block = None
    compiler.mutation_block(tree, None)
    Objects.path.assert_called_with(tree.path)
    Objects.mutation_fragment.assert_called_with(tree.service_fragment)
    Compiler.chained_mutations.assert_called_with(tree)
    args = [Objects.path(), Objects.mutation_fragment(), 'chained']
    kwargs = {'args': args, 'parent': None}
    lines.append.assert_called_with('mutation', tree.line(), **kwargs)


def test_compiler_indented_chain(patch, compiler, lines, tree):
    patch.object(Compiler, 'chained_mutations')
    lines.last.return_value = '1'
    lines.lines = {'1': {'method': 'mutation', 'args': ['args']}}
    compiler.indented_chain(tree, '0')
    Compiler.chained_mutations.assert_called_with(tree)
    assert lines.lines['1']['args'] == ['args'] + Compiler.chained_mutations()


def test_compiler_indented_chain_first_line(patch, compiler, lines, tree):
    """
    Ensures that if this is the first line, an error is raised.
    """
    patch.init(StorySyntaxError)
    lines.last.return_value = None
    with raises(StorySyntaxError):
        compiler.indented_chain(tree, '0')
    error = 'arguments_nomutation'
    StorySyntaxError.__init__.assert_called_with(error, tree=tree)


def test_compiler_indented_chain_not_mutation(patch, compiler, lines, tree):
    """
    Ensures that if the previous line is not a mutation, an error is raised.
    """
    patch.init(StorySyntaxError)
    patch.object(Compiler, 'chained_mutations')
    lines.last.return_value = '1'
    lines.lines = {'1': {'method': 'whatever'}}
    with raises(StorySyntaxError):
        compiler.indented_chain(tree, '0')
    error = 'arguments_nomutation'
    StorySyntaxError.__init__.assert_called_with(error, tree=tree)


def test_compiler_service_block(patch, compiler, tree):
    patch.object(Compiler, 'service')
    tree.node.return_value = None
    compiler.service_block(tree, '1')
    Compiler.service.assert_called_with(tree.service, tree.nested_block, '1')


def test_compiler_service_block_nested_block(patch, compiler, tree):
    patch.many(Compiler, ['subtree', 'service'])
    compiler.service_block(tree, '1')
    Compiler.subtree.assert_called_with(tree.nested_block, parent=tree.line())


def test_compiler_when_block(patch, compiler, tree):
    patch.many(Compiler, ['subtree', 'when'])
    compiler.when_block(tree, '1')
    Compiler.when.assert_called_with(tree, tree.nested_block, '1')


def test_compiler_when_block_nested_block(patch, compiler, tree):
    patch.many(Compiler, ['subtree', 'when'])
    compiler.when_block(tree, '1')
    Compiler.subtree.assert_called_with(tree.nested_block, parent=tree.line())


def test_compiler_try_block(patch, compiler, lines, tree):
    """
    Ensures that try blocks are compiled correctly.
    """
    patch.object(Compiler, 'subtree')
    tree.catch_block = None
    tree.finally_block = None
    compiler.try_block(tree, '1')
    kwargs = {'enter': tree.nested_block.line(), 'parent': '1'}
    lines.set_scope.assert_called_with(tree.line(), '1')
    lines.finish_scope.assert_called_with(tree.line())
    lines.append.assert_called_with('try', tree.line(), **kwargs)
    Compiler.subtree.assert_called_with(tree.nested_block, parent=tree.line())


def test_compiler_try_block_catch(patch, compiler, lines, tree):
    patch.many(Compiler, ['subtree', 'catch_block'])
    tree.finally_block = None
    compiler.try_block(tree, '1')
    Compiler.catch_block.assert_called_with(tree.catch_block, parent='1')


def test_compiler_try_block_finally(patch, compiler, lines, tree):
    patch.many(Compiler, ['subtree', 'finally_block'])
    tree.catch_block = None
    compiler.try_block(tree, '1')
    Compiler.finally_block.assert_called_with(tree.finally_block, parent='1')


def test_compiler_catch_block(patch, compiler, lines, tree):
    """
    Ensures that catch blocks are compiled correctly.
    """
    patch.object(Objects, 'names')
    patch.object(Compiler, 'subtree')
    compiler.catch_block(tree, '1')
    lines.set_exit.assert_called_with(tree.line())
    Objects.names.assert_called_with(tree.catch_statement)
    lines.set_scope.assert_called_with(tree.line(), '1', Objects.names())
    lines.finish_scope.assert_called_with(tree.line())
    kwargs = {'enter': tree.nested_block.line(), 'output': Objects.names(),
              'parent': '1'}
    lines.append.assert_called_with('catch', tree.line(), **kwargs)
    Compiler.subtree.assert_called_with(tree.nested_block, parent=tree.line())


def test_compiler_finally_block(patch, compiler, lines, tree):
    """
    Ensures that finally blocks are compiled correctly.
    """
    patch.object(Compiler, 'subtree')
    compiler.finally_block(tree, '1')
    lines.set_exit.assert_called_with(tree.line())
    lines.set_scope.assert_called_with(tree.line(), '1')
    lines.finish_scope.assert_called_with(tree.line())
    kwargs = {'enter': tree.nested_block.line(), 'parent': '1'}
    lines.append.assert_called_with('finally', tree.line(), **kwargs)
    Compiler.subtree.assert_called_with(tree.nested_block, parent=tree.line())


def test_compiler_break_statement(compiler, lines, tree):
    compiler.break_statement(tree, '1')
    lines.append.assert_called_with('break', tree.line(), parent='1')


def test_compiler_break_statement_outside(patch, compiler, lines, tree):
    compiler.break_statement(tree, None)
    tree.expect.assert_called_with(False, 'break_outside')


@mark.parametrize('method_name', [
    'service_block', 'absolute_expression', 'assignment', 'if_block',
    'elseif_block', 'else_block', 'foreach_block', 'function_block',
    'when_block', 'try_block', 'return_statement', 'arguments', 'imports',
    'mutation_block', 'indented_chain', 'break_statement'
])
def test_compiler_subtree(patch, compiler, method_name):
    patch.object(Compiler, method_name)
    tree = Tree(method_name, [])
    compiler.subtree(tree)
    method = getattr(compiler, method_name)
    method.assert_called_with(tree, None)


def test_compiler_subtree_parent(patch, compiler):
    patch.object(Compiler, 'assignment')
    tree = Tree('assignment', [])
    compiler.subtree(tree, parent='1')
    compiler.assignment.assert_called_with(tree, '1')


def test_compiler_subtrees(patch, compiler, tree):
    patch.object(Compiler, 'subtree', return_value={'tree': 'sub'})
    compiler.subtrees(tree, tree)
    compiler.subtree.assert_called_with(tree, parent=None)


def test_compiler_subtrees_parent(patch, compiler, tree):
    patch.object(Compiler, 'subtree', return_value={'tree': 'sub'})
    compiler.subtrees(tree, tree, parent='1')
    compiler.subtree.assert_called_with(tree, parent='1')


def test_compiler_parse_tree(compiler, patch):
    """
    Ensures that the parse_tree method can parse a complete tree
    """
    patch.object(Compiler, 'subtree')
    tree = Tree('start', [Tree('command', ['token'])])
    compiler.parse_tree(tree)
    compiler.subtree.assert_called_with(Tree('command', ['token']),
                                        parent=None)


def test_compiler_parse_tree_parent(compiler, patch):
    patch.object(Compiler, 'subtree')
    tree = Tree('start', [Tree('command', ['token'])])
    compiler.parse_tree(tree, parent='1')
    compiler.subtree.assert_called_with(Tree('command', ['token']), parent='1')


def test_compiler_compiler(patch):
    patch.init(Compiler)
    result = Compiler.compiler()
    assert isinstance(result, Compiler)


def test_compiler_compile(patch):
    patch.object(Preprocessor, 'process')
    patch.many(Compiler, ['parse_tree', 'compiler'])
    result = Compiler.compile('tree')
    Preprocessor.process.assert_called_with('tree')
    Compiler.compiler().parse_tree.assert_called_with(Preprocessor.process())
    lines = Compiler.compiler().lines
    expected = {'tree': lines.lines, 'version': version,
                'services': lines.get_services(), 'functions': lines.functions,
                'entrypoint': lines.first(), 'modules': lines.modules}
    assert result == expected
