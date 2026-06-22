; captures: function, call, import, class, interface
; Elixir uses 'call' nodes for all def/defmodule/defstruct etc.
; We capture the first argument as the name
(call target: (identifier) @call)
(unary_operator operator: "@" (call target: (identifier) @call))
(alias) @import
