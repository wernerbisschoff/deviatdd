; captures: function, class, interface, call, import, conditional, loop
(function_declaration name: (identifier) @function)
(class_declaration name: (type_identifier) @class)
(method_definition name: (property_identifier) @method)
(interface_declaration name: (type_identifier) @interface)
(type_alias_declaration name: (type_identifier) @interface)
(arrow_function) @function
(call_expression) @call
(import_statement) @import
(export_statement) @function
(if_statement) @conditional
(for_statement) @loop
(while_statement) @loop
(switch_statement) @conditional
