class Method:

    def __init__(self, method, parser, line_number, suite=None, output=None,
                 container=None, args=None, enter=None, exit=None):
        self.method = method
        self.parser = parser
        self.lineno = str(line_number)
        self.suite = suite
        self.output = output
        self.container = container
        self.args = args
        self.enter = enter
        self.exit = exit
