FROM continuumio/miniconda3:4.12.0
RUN apt update && apt upgrade -y
RUN apt-get update
RUN apt-get install -y gcc
RUN apt-get install -y curl
RUN apt-get install -y make
RUN apt-get install -y fonts-dejavu fontconfig
RUN apt-get install -y gnupg2
RUN apt-get install -y oathtool

RUN mkdir /DIAS
RUN mkdir /sencast

RUN curl -O http://step.esa.int/downloads/9.0/installers/esa-snap_all_unix_9_0_0.sh
RUN chmod 755 esa-snap_all_unix_9_0_0.sh
RUN echo "o\n1\n\n\nn\nn\nn\n" | bash esa-snap_all_unix_9_0_0.sh

RUN cd /opt/snap/snap/ && wget https://eawagrs.s3.eu-central-1.amazonaws.com/snap/snap_modules.tar.gz && tar -zxvf snap_modules.tar.gz
ENV SNAP_HOME=/opt/snap
RUN (timeout 250 $SNAP_HOME/bin/snap --nosplash --nogui --modules --update-all; exit 0)
RUN echo "#SNAP configuration 's3tbx'" >> /opt/snap/etc/s3tbx.properties
RUN echo "#Fri Mar 27 12:55:00 CET 2020" >> /opt/snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.olci.pixelGeoCoding=true" >> /opt/snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.meris.pixelGeoCoding=true" >> /opt/snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.slstrl1b.pixelGeoCodings=true" >> /opt/snap/etc/s3tbx.properties
RUN echo 'use.openjp2.jna=true' >> /root/.snap/etc/s2tbx.properties

COPY ./sencast.yml /sencast/
RUN conda env create -f /sencast/sencast.yml
ENV CONDA_HOME=/opt/conda
ENV CONDA_ENV_HOME=$CONDA_HOME/envs/sencast
ENV PYTHONUNBUFFERED=1

RUN mkdir /opt/POLYMER
COPY ./docker_dependencies/polymer-v4.15.tar.gz /opt/POLYMER/
RUN tar -xvzf /opt/POLYMER/polymer-v4.15.tar.gz -C /opt/POLYMER/
SHELL ["conda", "run", "-n", "sencast", "/bin/bash", "-c"]
RUN cd /opt/POLYMER/polymer-v4.15 && make all
RUN cp -avr /opt/POLYMER/polymer-v4.15/polymer $CONDA_ENV_HOME/lib/python3.7/site-packages/polymer
RUN cp -avr /opt/POLYMER/polymer-v4.15/auxdata $CONDA_ENV_HOME/lib/python3.7/site-packages/auxdata

RUN cd /opt &&  git clone --depth 1 --branch python37 https://github.com/JamesRunnalls/acolite.git

RUN mkdir /opt/FLUO
RUN apt-get install unzip
RUN cd /opt/FLUO && wget https://www.dropbox.com/s/ub3i66l4zqw51cs/snap-eum-fluo-1.0.nbm && unzip /opt/FLUO/snap-eum-fluo-1.0.nbm -d /opt/FLUO/snap-eum-fluo-1.0 && rm /opt/FLUO/snap-eum-fluo-1.0.nbm
RUN cp -r /opt/FLUO/snap-eum-fluo-1.0/netbeans/* ~/.snap/system

RUN mkdir /opt/ICOR
# RUN cd /opt/ICOR && wget https://ext.vito.be/icor/icor_install_ubuntu_20_04_x64_3.0.0.bin && chmod 755 icor_install_ubuntu_20_04_x64_3.0.0.bin && ./icor_install_ubuntu_20_04_x64_3.0.0.bin && rm icor_install_ubuntu_20_04_x64_3.0.0.bin

RUN mkdir /opt/SEN2COR
RUN cd /opt/SEN2COR && wget https://step.esa.int/thirdparties/sen2cor/2.11.0/Sen2Cor-02.11.00-Linux64.run --no-check-certificate && chmod 755 Sen2Cor-02.11.00-Linux64.run && ./Sen2Cor-02.11.00-Linux64.run && rm Sen2Cor-02.11.00-Linux64.run

RUN cd /opt && git clone --depth 1 --branch sencast https://gitlab.renkulab.io/eawagrs/ocsmart.git && cd /

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
