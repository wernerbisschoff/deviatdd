; captures: function, class, call, import, conditional, loop
(function_declaration name: (identifier) @function)
(class_declaration name: (identifier) @class)
(method_definition name: (property_identifier) @method)
(arrow_function) @function
(call_expression) @call
(import_statement) @import
(export_statement) @function
(if_statement) @conditional
(for_statement) @loop
(while_statement) @loop
(switch_statement) @conditional
