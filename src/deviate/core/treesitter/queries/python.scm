; captures: function, class, call, import, conditional, loop
(function_definition name: (identifier) @function)
(class_definition name: (identifier) @class)
(call (identifier) @call)
(import_statement) @import
(import_from_statement) @import
(if_statement) @conditional
(for_statement) @loop
(while_statement) @loop
(match_statement) @conditional
