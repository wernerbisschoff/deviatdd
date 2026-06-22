; captures: function, class, interface, call, import, conditional, loop
(function_item name: (identifier) @function)
(struct_item name: (type_identifier) @struct)
(enum_item name: (type_identifier) @enum)
(trait_item name: (type_identifier) @interface)
(impl_item) @class
(call_expression) @call
(use_declaration) @import
(if_expression) @conditional
(for_expression) @loop
(while_expression) @loop
(match_expression) @conditional
