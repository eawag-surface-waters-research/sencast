#!/bin/bash
downloads=1
processors=1
adapters=1
while getopts ":p:e:d:r:a:t" opt; do
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
    t) test="true"
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

if [[ -z "$test" ]]; then
  if [[ -z "$parameters" || -z "$environment" ]]; then
    echo "The parameters argument -p and the environment argument -e must be set."
  else
    echo "Running Sencast"
    cd /sencast
    conda activate sencast
    python main.py -p "$parameters" -e "$environment" -d "$downloads" -r "$processors" -a "$adapters"
  fi
else
  echo "Running Sencast Tests"
  cd /sencast
  conda activate sencast
  python tests/test_installation.py
fi


