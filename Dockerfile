FROM condaforge/miniforge3:25.3.1-0
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

RUN curl -O https://download.esa.int/step/snap/13.0/installers/esa-snap_all_linux-13.0.0.sh
RUN chmod 755 esa-snap_all_linux-13.0.0.sh
RUN echo "o\n1\n\n\nn\nn\nn\n" | bash esa-snap_all_linux-13.0.0.sh
RUN mv /opt/esa-snap /opt/snap

ENV SNAP_HOME=/opt/snap
RUN $SNAP_HOME/bin/snap --nosplash --nogui --modules --update-all
RUN $SNAP_HOME/bin/snap --nosplash --nogui --modules --install org.esa.snap.idepix.core org.esa.snap.idepix.landsat8 org.esa.snap.idepix.olci org.esa.snap.idepix.s2msi
RUN echo "#SNAP configuration 's3tbx'" >> /opt/snap/etc/s3tbx.properties
RUN echo "#Fri Mar 27 12:55:00 CET 2020" >> /opt/snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.olci.pixelGeoCoding=true" >> /opt/snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.meris.pixelGeoCoding=true" >> /opt/snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.slstrl1b.pixelGeoCodings=true" >> /opt/snap/etc/s3tbx.properties
RUN echo "s3tbx.landsat.readAs=reflectance" >> /root/.snap/etc/s3tbx.properties
RUN echo 'use.openjp2.jna=true' >> /root/.snap/etc/s2tbx.properties

COPY ./sencast.yml /sencast/
RUN conda env create -f /sencast/sencast.yml
ENV CONDA_HOME=/opt/conda
ENV CONDA_ENV_HOME=$CONDA_HOME/envs/sencast
ENV PYTHONUNBUFFERED=1

RUN mkdir /opt/POLYMER
RUN cd /opt/POLYMER && git clone --filter=blob:none --no-checkout https://github.com/hygeos/polymer.git polymer && git -C polymer checkout a7e40d04d110e7f99399620ee760e9565858a5f3
SHELL ["conda", "run", "-n", "sencast", "/bin/bash", "-c"]
RUN cd /opt/POLYMER/polymer && make all
RUN cp -avr /opt/POLYMER/polymer/polymer $CONDA_ENV_HOME/lib/python3.11/site-packages/polymer
RUN cp -avr /opt/POLYMER/polymer/auxdata $CONDA_ENV_HOME/lib/python3.11/site-packages/auxdata

RUN git clone --filter=blob:none --no-checkout https://github.com/acolite/acolite.git /opt/acolite && git -C /opt/acolite checkout fc3e0cce4f608cf998f7d83cb6d002bb32d43f1a

RUN cd /opt && git clone --depth 1 --branch sencast https://gitlab.eawag.ch/surf/remote-sensing/ocsmart.git && cd /

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
