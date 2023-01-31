#!/bin/bash
downloads=1
processors=1
adapters=1
while getopts ":p:e:d:r:a:s" opt; do
  case $opt in
    p) parameters="$OPTARG"
    ;;
    e) environment="$OPTARG"
    ;;
    d) downloads="$OPTARG"
    ;;
    r) processors="$OPTARG"
    ;;
    a) adapters="$OPTARG"
    ;;
    s) script="$OPTARG"
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    exit 1
    ;;
  esac

  case $OPTARG in
    -*) echo "Option $opt needs a valid argument"
    exit 1
    ;;
  esac
done

if [[ -z "$environment" ]]; then
  echo "The environment argument -e must be set."
else
  if [[ -z "$script" ]]; then
    if [[ -z "$parameters" ]]; then
      echo "The parameters argument -p must be set."
    else
      echo "Running Sencast"
      cd /sencast
      conda run -n sencast python main.py -p "$parameters" -e "$environment" -d "$downloads" -r "$processors" -a "$adapters"
    fi
  else
    echo "Running Sencast Tests"
    cd /sencast
    conda run -n sencast python -s "$script" -p "$parameters" -e "$environment"
  fi
fi




