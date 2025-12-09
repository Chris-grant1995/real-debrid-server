# Use an official Node.js runtime as a parent image
FROM node:18

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json to the working directory
COPY package*.json ./

# Install any needed dependencies
RUN npm install

# Copy the content of the local src directory to the working directory
COPY . .

ENV VITE_RCLONE_MOUNT_URL=http://localhost:8080/torrents

# Make port 5173 available to the world outside this container
EXPOSE 5173

# Run the app when the container launches
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
