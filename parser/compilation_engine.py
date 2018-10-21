from parser.utils import token_types
from parser.utils.fancy_objects import PlusEqualsableIterator
from parser.utils.exceptions import (
    CompileError,
    CompileKeywordError,
    CompileSymbolError,
    CompileTypeError,
    CompileClassVarDecError,
    CompileSubroutineError,
    CompileParameterListError,
    CompileSubroutineBodyError,
    CompileVarDecError,
    CompileLetError,
    CompileExpressionError,
    CompileOpError,
    CompileKeywordConstantError,
    CompileDoError,
    CompileSubroutineCallError,
    CompileReturnError,
    CompileIfError,
    CompileWhileError,
)


class CompilationEngine:
    """A recursive top-down parser for Jack.

    The *CompilationEngine* effects the actual compilation output.

    It gets its input from a `JackTokenizer` and emits its parsed structure into an output file/stream.

    The output is generated by a series of `compilexxx()` routines, one for every syntactic element `xxx` of the Jack grammar.

    The contract between these routines is that each `compilexxx()` routine should read the syntactic construct `xxx` from the input, `advance()` the tokenizer exactly beyond `xxx`, and output the parsing of `xxx`.
        Thus, `compilexxx()` may only be called if `xxx` is the next syntactic element of the input.

    In the first version of the compiler, which we now build, this module emits a structured printout of the code, wrapped in XML tags (defined in the specs of project 10). In the final version of the compiler, this module generates executable VM code (defined in the specs of project 11).

    In both cases, the parsing logic and module API are exactly the same.

    The syntax analyzer’s algorithm shown in this slide:
    If xxx is non-terminal, output:
        <xxx>
            Recursive code for the body of xxx
        </xxx>
    If xxx is terminal (keyword, symbol, constant, or identifier), output:
        <xxx>
            xxx value
        </xxx>

    """

    def __init__(self, infile, outfile):
        """Creates a new compilation engine with the given input and output.

        The next routine called must be `compile_class()`.
        """

        # I'm kind of confused about piping ...
        self._infile = infile
        self._outfile = outfile
        self._indent = 0
        self._body = PlusEqualsableIterator()  # iterator of all body elements.
        self._safe_to_step = True

    def compile_class(self):
        """Compiles a complete class.

        class: 'class' className '{' classVarDec* subroutineDec* '}'
        """
        current_element = 'class'

        self.add_keywords([current_element])  # step 1 - 'class'
        self.add_identifier('class name')  # step 2 - className
        self.add_symbols(['{'])  # step 3 - '{'

        # write start of element body
        self.write_non_terminal_start(current_element)

        while True:  # step 4 - classVarDec*
            try:
                self.compile_class_var_dec()  # step 4.i - classVarDec
            except CompileKeywordError:
                break

        # This compile has a dead first step!
        while True:  # step 5 - subroutineDec*
            try:
                self.compile_subroutine()  # step 5.i - subroutineDec
            except CompileKeywordError:
                break

        # Since the previous function stepped ahead on fail ...
        # don't step here.
        self.add_symbols(['}'])  # step 6 - '}'

        # write end of element body
        self.write_non_terminal_end(current_element)

    def compile_class_var_dec(self):
        """Compiles a static declaration or a field declaration.

        classVarDec: ('static' | 'field) type varName (, varName)* ';'
        """

        self.add_keywords(['static', 'field'])  # step 1 - ('static' | 'field)
        try:
            self.add_type_var_name_var_name()  # step 2-5 - type varName (, varName)* ';'
        except CompileError as ex:
            raise CompileClassVarDecError("Expected a complete static  or a field declaration: " + str(ex))

        # write element body
        self.write_non_terminal("classVarDec")

    def compile_subroutine(self):
        """Compiles a complete method, function or constructor.

        subroutineDec: ('constructor' | 'function' | 'method') ('void' | type) subroutineName '(' parameterList ')' subroutineBody

        NOTE: first step of first function is smothered.
        This is because the previous function failed + advanced an
        extra time.
        """
        current_element = "subroutineDec"

        # Previous call stepped ahead and extra time so don't step here.
        self.add_keywords(['constructor', 'function', 'method'])

        try:
            self.add_type(void=True)
            self.add_identifier('subroutine name')
            self.add_symbols(['('])

            self.write_non_terminal_start(current_element)  # write body start

            self.compile_parameter_list()  # new non-terminal

            # Previous method stepped ahead on fail so don't step here.
            # Needs special write call as this appears between two non-terminals?
            self.add_symbols([')'])
            self.write_body()

            self.compile_subroutine_body()
        except CompileError as ex:
            raise CompileSubroutineError("Expected a complete method, function or constructor declaration: " + str(ex))

        self.write_non_terminal_end(current_element)  # write body end

    def compile_parameter_list(self):
        """Compiles a (possibly empty) parameter list, not including the enclosing '( )'.

        parameterList: ((type varName)(',' type varName)*)?
        """

        while True:
            try:
                self.add_type()  # step 1 - type
            except CompileTypeError:
                break

            # If first case passes this one has to exist
            # This is the only real step to error check on.
            try:
                self.add_identifier('variable name')  # step 2 - varName
            except CompileError as ex:
                raise CompileParameterListError("Expected a complete parameter list declaration: " + str(ex))
            try:
                self.add_symbols([','])
            except CompileSymbolError:
                break

        self.write_non_terminal("parameterList")

    def compile_var_dec(self):
        """Compiles a `var` declaration.

        varDec: 'var' type varName (',' varName)* ';'
        """

        self.add_keywords(['var'])
        try:
            self.add_type_var_name_var_name()
        except CompileError as ex:
            raise CompileVarDecError("Expected a complete variable declaration: " + str(ex))
        self.write_non_terminal('varDec')

    def compile_subroutine_body(self):
        """Compiles a subroutine body.

        subroutineBody: '{' varDec* statements '}'
        """

        current_element = "subroutineBody"

        try:
            self.add_symbols(['{'])
            self.write_non_terminal_start(current_element)

            while True:
                try:
                    self.compile_var_dec()
                except CompileKeywordError:
                    break
            self.compile_statements()

            self.add_symbols(['}'])
        except CompileError as ex:
            raise CompileSubroutineBodyError("Expected a complete subroutine body declaration: " + str(ex))
        self.write_non_terminal_end(current_element)

    def compile_statements(self):
        """Compiles a sequence of statements, not including the enclosing '{ }'.

        statements: statement*
        statement: letStatement | ifStatement | whileStatement | doStatement |
            returnStatement
        """

        f = self._infile
        current_element = "statements"

        self.write_non_terminal_start(current_element)

        if f.token_type() == token_types.SYMBOL and f.symbol() == '{':
            f.advance()
            self._safe_to_step = False

        while f.token_type() == token_types.KEYWORD:
            if f.key_word() == token_types.LET:
                self.compile_let()
            elif f.key_word() == token_types.IF:
                self.compile_if()
            elif f.key_word() == token_types.WHILE:
                self.compile_while()
            elif f.key_word() == token_types.DO:
                self.compile_do()
            elif f.key_word() == token_types.RETURN:
                self.compile_return()
            else:
                raise CompileKeywordError("Expected let | if | while | do | return")
            if self._safe_to_step:
                f.advance()
                self._safe_to_step = False
            # self._safe_to_step = True
            # print("working out statements", f.token)

        self.write_non_terminal_end(current_element)

    def compile_do(self):
        """Compiles a `do` statement.

        doStatement: 'do' subroutineCall ';'
        """
        current_element = 'doStatement'

        try:
            self.add_keywords(['do'])
            self.write_non_terminal_start(current_element)

            self.add_subroutine_call()
            self.add_symbols([';'])
        except CompileError as ex:
            raise CompileDoError("Expected a complete do statement: " + str(ex))
        self.write_non_terminal_end(current_element)

    def compile_let(self):
        """Compiles a `let` statement.

        letStatement: 'let' varName ('[' expression ']')? = expression ';'
        """

        current_element = 'letStatement'

        try:
            self.add_keywords(['let'])
            self.add_identifier('variable name')
            self.write_non_terminal_start(current_element)

            # optional expression
            expression = True
            try:
                self.add_symbols(['['])
                self.write_body()
            except CompileSymbolError:
                expression = False

            # These should run as long as the previous step passes!
            if expression:
                self.compile_expression()
                self.add_symbols([']'])

            self.add_symbols(['='])  # requires special write method
            self.write_body()

            self.compile_expression()
            self.add_symbols([';'])
        except CompileError as ex:
            raise CompileLetError("Expected a complete let statement: " + str(ex))

        self.write_non_terminal_end(current_element)

    def compile_while(self):
        """Compiles a `while` statement.

        whileStatement: 'while' '(' expression ')' '{' statements '}
        """

        current_element = 'whileStatement'

        try:
            self.add_keywords(['while'])
            self.add_symbols(['('])
            self.write_non_terminal_start(current_element)
            self.compile_expression()
            self.add_symbols([')'])
            self.add_symbols(['{'])
            self.write_body()
            self.compile_statements()
            self.add_symbols(['}'])
        except CompileError as ex:
            raise CompileWhileError("Exprected a complete while statement: " + str(ex))

        self.write_non_terminal_end(current_element)

    def compile_return(self):
        """Compiles a `return` statement.

        returnStatement: 'return' expression? ';'
        """

        current_element = 'returnStatement'

        try:
            self.add_keywords(['return'])
            self.write_non_terminal_start(current_element)

            try:
                self.add_symbols([';'])  # if next element is ';', just move on.
            except CompileSymbolError:  # if it wasn't it should be an expression
                try:
                    self.compile_expression()  # optional expression
                except CompileExpressionError:
                    pass
                self.add_symbols([';'])  # followed by a ';'
        except CompileError as ex:
            raise CompileReturnError("Expected a complete return statement: " + str(ex))
        self.write_non_terminal_end(current_element)

    def compile_if(self):
        """Compiles an `if` statement, possibly with a trailing `else` clause.

        ifStatement: 'if' '(' expression ')' '{' statements '}' ('else' '{' statements '}')?
        """

        current_element = 'ifStatement'
        f = self._infile

        try:
            self.add_keywords(['if'])
            self.add_symbols(['('])
            self.write_non_terminal_start(current_element)

            self.compile_expression()
            self.add_symbols([')'])
            self.add_symbols(['{'])
            self.write_body()

            self.compile_statements()
            self.add_symbols(['}'])

            f.advance()
            self._safe_to_step = False
            if f.token_type() == token_types.KEYWORD and f.key_word() == token_types.ELSE:
                self.add_keywords(['else'])
                self.add_symbols(['{'])
                self.write_body()
                self.compile_statements()
                self.add_symbols(['}'])
        except CompileError as ex:
            raise CompileIfError("Expected a complete if statement: " + str(ex))

        self.write_non_terminal_end(current_element)

    def compile_expression(self):
        """Compiles an `expression`.

        term (op term)*
        """

        current_element = "expression"
        self.write_non_terminal_start(current_element)

        try:
            self.compile_term()

            while True:
                try:
                    self.add_op_or_unary_op()
                    self.write_body()
                    self.compile_term()
                except CompileOpError:
                    break  # no (op term)* exists!
        except CompileError as ex:
            raise CompileExpressionError("Expected a complete expression: " + str(ex))
        self.write_non_terminal_end(current_element)

    def compile_term(self):
        """Compiles a `term`.

        This routine is faced with a slight difficulty when trying to decide between some of the alternative parsing rules. Specifically, if the current token is an identifier, the routine must distinguish between a variable, an array entry, and a subroutine call. A single look-ahead token, which may be one of "[", "{" or "." suffices to distinguish between the three possibilities. Any other token is not part of this term and should not be advanced over.

        term: integerConstant | stringConstant | keywordConstant | varName | varName '[' expression ']' | subroutineCall | '(' expression ')' | unaryOp term
        """
        f = self._infile
        current_element = "term"
        self.write_non_terminal_start(current_element)

        if self._safe_to_step:
            f.advance()
            self._safe_to_step = False

        if f.token_type() == token_types.INT_CONST:
            self._body += ['integerConstant', f.int_val()]
            self._safe_to_step = True
        elif f.token_type() == token_types.STRING_CONST:
            self._body += ['stringConstant', f.string_val()]
            self._safe_to_step = True
        elif f.token_type() == token_types.KEYWORD:
            self.add_keyword_constant()
        elif f.token_type() == token_types.IDENTIFIER:
            self.add_identifier('variable name | subroutine name | class name')
            f.advance()
            self._safe_to_step = False
            if f.token_type() == token_types.SYMBOL:
                if f.symbol() == '[':
                    self.add_symbols(['['])  # requires special write
                    self.write_body()
                    self.compile_expression()
                    self.add_symbols([']'])
                elif f.symbol() == '(':
                    self.add_symbols(['('])  # requires special write
                    self.write_body()
                    self.compile_expression_list()
                    self.add_symbols([')'])
                elif f.symbol() == '.':
                    self.add_symbols(['.'])
                    self.write_body()
                    self.add_subroutine_call()
        elif f.token_type() == token_types.SYMBOL:
            if f.symbol() == '(':
                self.add_symbols(['('])  # requires special write
                self.write_body()
                self.compile_expression()
                self.add_symbols([')'])
            elif f.symbol() in ['-', '~']:
                self.add_op_or_unary_op(unary=True)  # requires special write
                self.write_body()
                self.compile_term()
            # else:
            #     raise CompileTermError("")

        self.write_non_terminal_end('term')

    def compile_expression_list(self):
        """Compiles a (possibly empty) comma-separated list of expressions.

        (expression (',' expression)*)?
        """
        current_element = 'expressionList'
        f = self._infile

        self.write_non_terminal_start(current_element)
        if self._safe_to_step:
            f.advance()
            self._safe_to_step = False

        while f.token_type() == token_types.SYMBOL and f.symbol() != ')' or f.token_type() != token_types.SYMBOL:  # might need modification?
            try:
                self.compile_expression()
            except CompileExpressionError:
                break

            try:
                self.add_symbols([','])
                self.write_body()
            except CompileSymbolError:
                break

        self.write_non_terminal_end(current_element)

    def add_subroutine_call(self):
        """Add a subroutine call.

        subroutineCall: subroutineName '(' expressionList ')' | (className | varName) '.' subroutineName '(' expressionList ')'
        """
        f = self._infile

        try:
            self.add_identifier('subroutine name | class name | variable name')  # requires special write
            # try:
            self.add_symbols(['(', '.'])  # requires special write
            # except CompileSymbolError:
            #     pass  # I guess there was no period after all!
            self.write_body()
            if f.token_type() == token_types.SYMBOL:
                if f.symbol() == '(':
                    self.compile_expression_list()
                    self.add_symbols([')'])
                elif f.symbol() == '.':
                    self.add_subroutine_call()
        except CompileError as ex:
            raise CompileSubroutineCallError("Expected a complete subroutine call: " + str(ex))

    def add_keyword_constant(self):
        try:
            self.add_keywords(['true', 'false', 'null', 'this'])
        except CompileError as ex:
            raise CompileKeywordConstantError("Expected a keyword constant: " + str(ex))

    def add_op_or_unary_op(self, unary=False):
        """Add an operator (symbol).

        op: '+' | '-' | '*' | '/' | '&' | '|' | '<' | '>' | '='
        """
        f = self._infile

        try:
            if unary:
                self.add_symbols(['-', '~'])
            else:
                self.add_symbols((f.XML_ESCAPES[char] if char in f.XML_ESCAPES else char for char in ['+', '-', '*', '/', '&', '|', '<', '>', '=']))
        except CompileError as ex:
            raise CompileOpError("Expected an operator: " + str(ex))

    def add_type_var_name_var_name(self):
        """Add a type variable name list declaration.

        type varName (',' varName)* ;
        """

        f = self._infile
        self.add_type()  # step 1 - type
        self.add_identifier('variable name')  # step 2 - varName

        # step 3/4 - (',' varName)* ';'
        # I merged these steps for convenience.
        more_vars = True
        while more_vars:
            self.add_symbols([',', ';'])  # (',' varName)* ';'
            if f.symbol() == ';':
                more_vars = False
            else:
                self.add_identifier('variable name')

    def add_type(self, void=False):
        """Add a type declaration.

        type: 'int' | 'char' | 'boolean' | className
        """
        f = self._infile
        valid_types = [token_types.INT, token_types.CHAR, token_types.BOOLEAN]
        if void:
            valid_types.append(token_types.VOID)

        if self._safe_to_step:
            f.advance()
            self._safe_to_step = False

        if f.token_type() == token_types.KEYWORD and any([f.key_word() == type_ for type_ in valid_types]):
            terminal = f.NAMES_TABLE[f.key_word()]
            self._body += ['keyword', terminal]
            self._safe_to_step = True
        elif f.token_type() == token_types.IDENTIFIER:
            self._body += ['identifier', f.identifier()]
            self._safe_to_step = True
        else:
            expected = "| ".join(["'{}'".format(typ) for typ in valid_types + ['className']])
            raise CompileTypeError("Expected {}".format(expected))

    def add_keywords(self, keywords):
        """Add keyword(s) definition to body element."""
        f = self._infile

        if self._safe_to_step:
            f.advance()
            self._safe_to_step = False

        if f.token_type() == token_types.KEYWORD and any([f.key_word() == f.KEYWORDS_TABLE[key] for key in keywords]):
            terminal = f.NAMES_TABLE[f.key_word()]
            self._body += ['keyword', terminal]
            self._safe_to_step = True
        else:
            expected = "| ".join(["'{}'".format(key) for key in keywords])
            raise CompileKeywordError("Expected {}".format(expected))

    def add_symbols(self, symbols):
        """Add symbol definition to body element."""
        f = self._infile

        if self._safe_to_step:
            f.advance()
            self._safe_to_step = False

        if f.token_type() == token_types.SYMBOL and any([f.symbol() == sym for sym in symbols]):
            self._body += ['symbol', f.symbol()]
            self._safe_to_step = True
        else:
            expected = "| ".join(["'{}'".format(sym) for sym in symbols])
            raise CompileSymbolError("Expected {}".format(expected))

    def add_identifier(self, identifier):
        """Add identifier definition to body element."""
        f = self._infile

        if self._safe_to_step:
            f.advance()
            self._safe_to_step = False

        if f.token_type() == token_types.IDENTIFIER:
            self._body += ['identifier', f.identifier()]
            self._safe_to_step = True
        else:
            raise CompileError("Expected a {}".format(identifier))

    def write_body(self):
        for inner_element, terminal in self._body:  # write all body
            self._outfile.write(' ' * self._indent)
            self.write_terminal(inner_element, terminal)

    def write_terminal(self, element, terminal, indent=False):
        """Write a terminating xml element."""
        if indent:
            self._outfile.write(' ' * self._indent)
        print('<{element}> {terminal} </{element}>'.format(element=element, terminal=terminal), file=self._outfile)

    def write_non_terminal_start(self, element):
        """Write the start of a non-terminating xml element.

        uses self._body generator.
        """
        self._outfile.write(' ' * self._indent)
        print("<{}>".format(element), file=self._outfile)

        self._indent += 2  # on every body section increase indent.
        self.write_body()

    def write_non_terminal_end(self, element):
        """Write the end of a non-terminating xml element."""

        # write any trailing body elements.
        self.write_body()
        self._indent -= 2  # after every body section decrease indent.
        self._outfile.write(' ' * self._indent)
        print("</{}>".format(element), file=self._outfile)

    def write_non_terminal(self, element):
        """Write a non-terminating xml element.

        uses self._body generator.
        """
        self.write_non_terminal_start(element)
        self.write_non_terminal_end(element)
