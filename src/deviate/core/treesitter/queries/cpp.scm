; captures: function, class, call, import, conditional, loop
(function_definition declarator: (function_declarator declarator: (identifier) @function))
(class_specifier name: (type_identifier) @class)
(call_expression) @call
(using_declaration) @import
(if_statement) @conditional
(for_statement) @loop
(while_statement) @loop
(switch_statement) @conditional
