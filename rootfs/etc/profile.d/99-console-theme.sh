# Оформление консоли: цветное приглашение и удобные умолчания
# Маркеры \[ \] обязательны: без них bash неверно считает длину строки
# и ломает перенос при длинных командах.
if [ -n "$BASH_VERSION" ] && [ -t 1 ]; then
  _c_reset=$'\001\033[0m\002'
  _c_user=$'\001\033[38;5;110m\002'
  _c_at=$'\001\033[38;5;242m\002'
  _c_host=$'\001\033[38;5;79m\002'
  _c_path=$'\001\033[38;5;180m\002'
  _c_root=$'\001\033[38;5;203m\002'
  if [ "$EUID" = 0 ]; then
    PS1='${_c_user}\u${_c_at}@${_c_host}\h ${_c_path}\w ${_c_root}#${_c_at} ${_c_reset}'
  else
    PS1='${_c_user}\u${_c_at}@${_c_host}\h ${_c_path}\w${_c_at} \$ ${_c_reset}'
  fi
  PS2='${_c_at}> ${_c_reset}'
  export PS1 PS2
fi
# удобные умолчания
alias ls='ls --color=auto'
alias ll='ls -alF --color=auto'
alias grep='grep --color=auto'
alias df='df -h'
alias free='free -h'
