; captures: function, class, interface, call, import, conditional, loop
(function_declaration name: (identifier) @function)
(class_declaration name: (type_identifier) @class)
(protocol_declaration name: (type_identifier) @interface)
(call_expression) @call
(import_declaration) @import
(if_statement) @conditional
(for_statement) @loop
(while_statement) @loop
(switch_statement) @conditional
