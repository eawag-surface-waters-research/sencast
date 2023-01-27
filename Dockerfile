FROM continuumio/miniconda3:4.12.0
RUN apt update && apt upgrade -y
RUN apt-get update
RUN apt-get install -y gcc
RUN apt-get install -y curl
RUN apt-get install -y make
RUN apt-get install -y fonts-dejavu fontconfig

RUN mkdir /DIAS
RUN mkdir /sencast
RUN mkdir /programfiles
COPY ./adapters /sencast/adapters
COPY ./dias_apis /sencast/dias_apis
COPY ./mosaic /sencast/mosaic
COPY ./postprocess /sencast/postprocess
COPY ./processors /sencast/processors
COPY ./parameters/test_* /sencast/parameters
COPY ./utils /sencast/utils
COPY ./wkt /sencast/wkt
COPY ./constants.py /sencast/
COPY ./main.py /sencast/
COPY ./sencast.yml /sencast/

RUN conda env create -f /sencast/sencast.yml
ENV CONDA_HOME=/opt/conda
ENV CONDA_ENV_HOME=$CONDA_HOME/envs/sencast

RUN curl -O http://step.esa.int/downloads/9.0/installers/esa-snap_all_unix_9_0_0.sh
RUN chmod 755 esa-snap_all_unix_9_0_0.sh
RUN echo "o\n1\n\n\nn\nn\nn\n" | bash esa-snap_all_unix_9_0_0.sh
ENV SNAP_HOME=/opt/snap
# RUN $SNAP_HOME/bin/snap --nosplash --nogui --modules --update-all
# RUN $SNAP_HOME/bin/snap --nosplash --nogui --modules --install org.esa.snap.idepix.core org.esa.snap.idepix.probav org.esa.snap.idepix.modis org.esa.snap.idepix.spotvgt org.esa.snap.idepix.landsat8 org.esa.snap.idepix.viirs org.esa.snap.idepix.olci org.esa.snap.idepix.seawifs org.esa.snap.idepix.meris org.esa.snap.idepix.s2msi
RUN echo "#SNAP configuration 's3tbx'" >> /opt/snap/etc/s3tbx.properties
RUN echo "#Fri Mar 27 12:55:00 CET 2020" >> /opt/snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.olci.pixelGeoCoding=true" >> /opt/snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.meris.pixelGeoCoding=true" >> /opt/snap/etc/s3tbx.properties
RUN echo "s3tbx.reader.slstrl1b.pixelGeoCodings=true" >> /opt/snap/etc/s3tbx.properties

RUN mkdir /programfiles/POLYMER
COPY ./docker_dependencies/polymer-v4.15.tar.gz /programfiles/POLYMER/
RUN tar -xvzf /programfiles/POLYMER/polymer-v4.15.tar.gz -C /programfiles/POLYMER/
SHELL ["conda", "run", "-n", "sencast", "/bin/bash", "-c"]
RUN cd /programfiles/POLYMER/polymer-v4.15 && make all
RUN cp -avr /programfiles/POLYMER/polymer-v4.15/polymer $CONDA_ENV_HOME/lib/python3.7/site-packages/polymer
RUN cp -avr /programfiles/POLYMER/polymer-v4.15/auxdata $CONDA_ENV_HOME/lib/python3.7/site-packages/auxdata

COPY ./docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]
